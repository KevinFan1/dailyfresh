from django.shortcuts import render
from django.views import View
from django.http import JsonResponse
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
from apps.goods.models import GoodsSKU


class CartAddView(View):
    '''
    购物车记录添加
    添加商品到购物车
    1) 请求方式，采用ajax post
    2) 传递参数: 商品id(sku_id) 商品数量 count
    '''

    def post(self, request):
        '''购物车记录添加'''
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res': 0, 'errormsg': '请先登录用户'})

        # 接收收据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 校验数据
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errormsg': '数据不完整'})

        # 校验添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errormsg': '商品数目出错'})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errormsg': '商品不存在'})

        # 业务处理：添加购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 尝试获取sku_id的值 -> hget cart_key属性
        # 如果sku_id在hash中不存在，hget返回None
        cart_count = conn.hget(cart_key, sku_id)

        if cart_count:
            # 累加购物车中商品的数目
            count += int(cart_count)
        # 校验商品库存
        if count > sku.inventory:
            return JsonResponse({'res': 4, 'errormsg': '商品库存不足'})
        # 设置hash中sku_id对应的值
        conn.hset(cart_key, sku_id, count)

        # 计算用户购物车商品的条目数
        total_count = conn.hlen(cart_key)
        # 返回应答
        return JsonResponse({'res': 5, 'total_count': total_count, 'message': '添加商品成功'})


# /cart/
class CartInfoView(View, LoginRequiredMixin):
    '''购物车页面显示'''

    def get(self, request):
        # 获取登录的用户
        user = request.user
        # 获取用户购物车中的商品信息
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        cart_dict = conn.hgetall(cart_key)
        # 遍历获取商品的信息
        skus = []
        # 保存用户购物车中商品的总数目和价格
        total_count = 0
        total_price = 0
        for sku_id, count in cart_dict.items():
            # 根据商品的id获取商品的信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 计算商品的小计
            amount = sku.price * int(count)
            # 动态给sku对象增加一个属性amount,保存小计
            sku.amount = amount
            # 动态给sku对象增加一个属性count,保存数量
            sku.count = int(count)
            # 添加
            skus.append(sku)
            # 累加
            total_count += int(count)
            total_price += amount
        # 组织上下文传递的参数
        context = {
            'total_count': total_count,
            'total_price': total_price,
            'skus': skus,
        }
        return render(request, 'cart.html', context)


# 更新购物车记录
# 采用ajax post请求
# 前端需要传递的参数，商品id，数量
# /cart/update
class CartUpdateView(View):
    '''购物车记录更新'''

    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res': 0, 'errormsg': '请先登录用户'})
        # 接收收据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 校验数据
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errormsg': '数据不完整'})

        # 校验添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errormsg': '商品数目出错'})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errormsg': '商品不存在'})

        # 业务处理：更新购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 校验商品库存
        if count > sku.inventory:
            return JsonResponse({'res': 4, 'errormsg': '商品库存不足'})
        # 更新
        conn.hset(cart_key, sku_id, count)

        # 计算用户购物车中商品的总件数
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)

        # 返回应答
        return JsonResponse({'res': 5, 'total_count': total_count, 'message': '更新成功'})


# 更新购物车记录
# 采用ajax post请求
# 前端需要传递的参数，商品id
# /cart/delete
class CartDeleteView(View):
    '''购物车记录删除'''

    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res': 0, 'errormsg': '请先登录用户'})
        # 接收参数
        sku_id = request.POST.get('sku_id')
        if not sku_id:
            return JsonResponse({'res': 1, 'errormsg': '无效的商品id'})
        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errormsg': '商品不存在'})

        # 业务处理:删除记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        conn.hdel(cart_key, sku_id)

        # 计算用户购物车中商品的总件数
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)
        # 返回应答
        return JsonResponse({'res': 3, 'total_count': total_count, 'message': '商品删除成功'})
