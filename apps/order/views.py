import os
import time
from datetime import datetime
from django.db import transaction
from django.shortcuts import render, reverse, redirect
from django.views import View
from django_redis import get_redis_connection
from django.http import JsonResponse
from apps.goods.models import GoodsSKU
from apps.order.models import OrderInfo, OrderGoods
from apps.user.models import Address
from utils.mixin import LoginRequiredMixin
from alipay import AliPay
from django.conf import settings


# /order/place
class OrderPlaceView(View, LoginRequiredMixin):
    '''提交订单页面显示  悲观锁'''

    def post(self, request):
        # 获取登录的用户
        user = request.user
        # 获取参数sku_ids
        sku_ids = request.POST.getlist('sku_ids')
        # 校验参数
        if not sku_ids:
            # 跳转到购物车页面
            return redirect(reverse('cart:show'))
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        skus = []
        total_count = 0  # 总件数
        total_price = 0  # 总价格
        # 遍历sku_ids
        for sku_id in sku_ids:
            # 根据商品id获取商品信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 获取用户所需要购买的商品数量
            count = conn.hget(cart_key, sku_id)
            # 商品小计
            amount = sku.price * int(count)
            # 动态保存购买数量和小计
            sku.count = int(count)
            sku.amount = amount
            skus.append(sku)
            total_count += int(count)
            total_price += amount

        # 运费
        transit_price = 10
        # 实付款
        total_pay = total_price + transit_price
        # 获取用户的收件地址
        addrs = Address.objects.filter(user=user)
        sku_ids = ','.join(sku_ids)
        context = {
            'skus': skus,
            'total_count': total_count,
            'total_price': total_price,
            'transit_price': transit_price,
            'total_pay': total_pay,
            'addrs': addrs,
            'sku_ids': sku_ids,
        }
        return render(request, 'place_order.html', context)


# params = {'addr_id': addr_id,'pay_style': pay_style,'csrfmiddlewaretoken': csrf,'sku_ids': sku_ids,};
class OrderCommitView(View):
    '''订单创建 乐观锁'''

    @transaction.atomic
    def post(self, request):
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res': 0, 'errormsg': '请先登录用户'})
        # 接收参数
        addr_id = request.POST.get('addr_id')
        pay_style = request.POST.get('pay_style')
        sku_ids = request.POST.get('sku_ids')

        # 校验参数
        if not all([addr_id, pay_style, sku_ids]):
            return JsonResponse({'res': 1, 'errormsg': '数据不完整'})

        # 校验支付方式
        if pay_style not in OrderInfo.PAY_METHOD_DIC.keys():
            return JsonResponse({'res': 2, 'errormsg': '非法的支付方式'})
        # 校验支付方式
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res': 3, 'errormsg': '非法的收货地址'})

        # todo:创建订单
        # 订单id 日期 + user.id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        # 运费
        transit_price = 10
        total_count = 0
        total_price = 0

        # 设置事务保存点
        save_id = transaction.savepoint()
        try:
            # todo:创建一个订单记录,df_order_info
            order = OrderInfo.objects.create(order_id=order_id, user=user, addr=addr, pay_method=pay_style,
                                             total_count=total_count,
                                             total_price=total_price, transit_price=transit_price)
            # todo:订单中有几个商品，就加入几个记录 df_goods_order
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                for i in range(3):
                    # 获取商品信息
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except GoodsSKU.DoesNotExist:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 4, 'errormsg': '商品不存在'})
                    # 从redis中获取用户所需要购买的商品的数量
                    count = conn.hget(cart_key, sku_id)

                    # todo:判断商品库存
                    if int(count) > sku.inventory:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 6, 'errormsg': '商品库存不足'})

                    # todo:更新商品的库存和销量
                    orgin_inventory = sku.inventory
                    new_inventory = orgin_inventory - int(count)
                    new_sales = sku.sales + int(count)

                    # 更新库存和销量情况
                    # 返回受影响的行数,0或者1
                    res = GoodsSKU.objects.filter(id=sku_id, inventory=orgin_inventory).update(inventory=new_inventory,
                                                                                               sales=new_sales)
                    if res == 0:
                        if i == 2:
                            # 尝试的第三次如果还失败的情况
                            transaction.savepoint_rollback(save_id)
                            return JsonResponse({'res': 8, 'errormsg': '下单失败'})
                        continue

                    # todo:向df_goods_order添加记录
                    OrderGoods.objects.create(order_info=order, count=count, sku=sku, price=sku.price)

                    # todo:更新商品的库存和销量
                    sku.inventory -= int(count)
                    sku.sales += int(count)
                    sku.save()

                    # todo:累加计算商品的总数量和价格
                    amount = sku.price * int(count)
                    total_count += int(count)
                    total_price += amount

                    # 跳出循环
                    break

            # todo:更新df_order_info表中的总数量和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errormsg': '下单失败'})

        # 提交事务
        transaction.savepoint_commit(save_id)

        # todo:清除用户购物车中对应的记录 sku_ids = [1,2,3]，用*号会变成 1,2,3
        conn.hdel(cart_key, *sku_ids)

        return JsonResponse({'res': 5, 'message': '订单创建成功'})

    class OrderCommitView(View):
        '''订单创建'''

        @transaction.atomic
        def post(self, request):
            # 判断用户是否登录
            user = request.user
            if not user.is_authenticated:
                # 用户未登录
                return JsonResponse({'res': 0, 'errormsg': '请先登录用户'})
            # 接收参数
            addr_id = request.POST.get('addr_id')
            pay_style = request.POST.get('pay_style')
            sku_ids = request.POST.get('sku_ids')

            # 校验参数
            if not all([addr_id, pay_style, sku_ids]):
                return JsonResponse({'res': 1, 'errormsg': '数据不完整'})

            # 校验支付方式
            if pay_style not in OrderInfo.PAY_METHOD_DIC.keys():
                return JsonResponse({'res': 2, 'errormsg': '非法的支付方式'})
            # 校验支付方式
            try:
                addr = Address.objects.get(id=addr_id)
            except Address.DoesNotExist:
                return JsonResponse({'res': 3, 'errormsg': '非法的收货地址'})

            # todo:创建订单
            # 订单id 日期 + user.id
            order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
            # 运费
            transit_price = 10
            total_count = 0
            total_price = 0

            # 设置事务保存点
            save_id = transaction.savepoint()
            try:
                # todo:创建一个订单记录,df_order_info
                order = OrderInfo.objects.create(order_id=order_id, user=user, addr=addr, pay_method=pay_style,
                                                 total_count=total_count,
                                                 total_price=total_price, transit_price=transit_price)
                # todo:订单中有几个商品，就加入几个记录 df_goods_order
                conn = get_redis_connection('default')
                cart_key = 'cart_%d' % user.id
                sku_ids = sku_ids.split(',')
                for sku_id in sku_ids:
                    # 获取商品信息
                    try:
                        # select * from table where id = skuid for update; sql加锁
                        sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                    except GoodsSKU.DoesNotExist:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 4, 'errormsg': '商品不存在'})
                    # 从redis中获取用户所需要购买的商品的数量
                    count = conn.hget(cart_key, sku_id)

                    # todo:判断商品库存
                    if int(count) > sku.inventory:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 6, 'errormsg': '商品库存不足'})

                    # todo:向df_goods_order添加记录
                    OrderGoods.objects.create(order_info=order, count=count, sku=sku, price=sku.price)

                    # todo:更新商品的库存和销量
                    sku.inventory -= int(count)
                    sku.sales += int(count)
                    sku.save()

                    # todo:累加计算商品的总数量和价格
                    amount = sku.price * int(count)
                    total_count += int(count)
                    total_price += amount

                # todo:更新df_order_info表中的总数量和总价格
                order.total_count = total_count
                order.total_price = total_price
                order.save()
            except Exception as e:
                transaction.savepoint_rollback(save_id)
                return JsonResponse({'res': 7, 'errormsg': '下单失败'})

            # 提交事务
            transaction.savepoint_commit(save_id)

            # todo:清除用户购物车中对应的记录 sku_ids = [1,2,3]，用*号会变成 1,2,3
            conn.hdel(cart_key, *sku_ids)

            return JsonResponse({'res': 5, 'message': '订单创建成功'})


# /order/pay/
class OrderPayView(View):
    '''订单支付'''

    def post(self, request):
        # 用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errormsg': '用户尚未登录'})
        # 接收参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errormsg': '无效订单号'})
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user, pay_method=3, order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errormsg': '订单错误'})
        # 业务处理：调用alipay支付接口
        app_private_key_string = open(os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem')).read()
        alipay_public_key_string = open(os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem')).read()
        alipay = AliPay(
            appid="2016102000727504",
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key_string,
            alipay_public_key_string=alipay_public_key_string,
            sign_type="RSA2",
            debug=True,  # 上线则改为False , 沙箱True
        )

        # 调用接口(传参订单号和总价,标题)
        total_pay = order.total_price + order.transit_price
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=str(total_pay),
            subject='daily fresh order:%s' % order_id,
            return_url=None,
            notify_url=None,
        )
        # 拼接应答地址
        pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
        return JsonResponse({'res': 3, 'pay_url': pay_url})


# /order/check
class CheckPayView(View):
    '''查看订单支付的结果'''

    def post(self, request):
        # 用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errormsg': '用户尚未登录'})
        # 接收参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errormsg': '无效订单号'})
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user, pay_method=3, order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errormsg': '订单错误'})
        # 业务处理：调用alipay支付接口
        app_private_key_string = open(os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem')).read()
        alipay_public_key_string = open(os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem')).read()
        alipay = AliPay(
            appid="2016102000727504",
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key_string,
            alipay_public_key_string=alipay_public_key_string,
            sign_type="RSA2",
            debug=True,  # 上线则改为False , 沙箱True
        )
        while True:
            # 调用接口
            response = alipay.api_alipay_trade_query(order_id)
            """
                    response = {
                      "alipay_trade_query_response": {
                        "trade_no": "2017032121001004070200176844",
                        "code": "10000",
                        "invoice_amount": "20.00",
                        "open_id": "20880072506750308812798160715407",
                        "fund_bill_list": [
                          {
                            "amount": "20.00",
                            "fund_channel": "ALIPAYACCOUNT"
                          }
                        ],
                        "buyer_logon_id": "csq***@sandbox.com",
                        "send_pay_date": "2017-03-21 13:29:17",
                        "receipt_amount": "20.00",
                        "out_trade_no": "out_trade_no15",
                        "buyer_pay_amount": "20.00",
                        "buyer_user_id": "2088102169481075",
                        "msg": "Success",
                        "point_amount": "0.00",
                        "trade_status": "TRADE_SUCCESS",
                        "total_amount": "20.00"
                      },
                      "sign": ""
                    }
                    """
            code = response.get('code')
            trade_status = response.get('trade_status')
            if code == '10000' and trade_status == 'TRADE_SUCCESS':
                # 支付成功
                # 获取支付宝交易号
                trade_no = response.get('trade_no')
                order.trade_no = trade_no
                order.order_status = 4  # 待评价
                order.save()
                return JsonResponse({'res': 3, 'message': '支付成功'})
            elif (code == '10000' and trade_status == 'WAIT_BUYER_PAY') or code == '40004':
                time.sleep(5)
                continue
            else:
                return JsonResponse({'res': 4, 'errormsg': '支付失败'})


class CommentView(LoginRequiredMixin, View):
    def get(self, request, order_id):
        '''提供评论页面'''
        user = request.user
        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except:
            return redirect(reverse('user:order'))

        # 根据状态获取标题
        order.status_name = OrderInfo.ORDER_STATUS_DIC[order.order_status]
        # 获取订单商品信息
        order_skus = OrderGoods.objects.filter(order_info_id=order.id)
        print(order_skus)
        for order_sku in order_skus:
            amount = order_sku.count * order_sku.price
            # 小计
            order_sku.amount = amount
        # 动态增加order_skus,保存订单商品信息
        order.order_skus = order_skus

        return render(request, 'order_comment.html', {'order': order})

    def post(self, request, order_id):
        '''处理评论内容'''
        user = request.user
        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except:
            return redirect(reverse('user:order'))

        # 获取评论条数
        total_count = int(request.POST.get('total_count'))

        for i in range(1, total_count + 1):
            # 评论商品id
            sku_id = request.POST.get('sku_%d' % i)
            # 评论商品内容
            content = request.POST.get('content_%d' % i, '')
            try:
                order_goods = OrderGoods.objects.get(order_info=order, sku=sku_id)
            except OrderGoods.DoesNotExist:
                continue

            order_goods.comment = content
            order_goods.save()
        order.order_status = 5
        order.save()
        return redirect(reverse('user:order', kwargs={'page': 1}))
