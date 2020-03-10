from django.shortcuts import render, redirect, reverse
from django.http import HttpResponse
import re
from django.views.generic import View
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from django.core.paginator import Paginator
from apps.order.models import OrderInfo, OrderGoods
from .models import User, Address
from django.conf import settings
from celery_tasks.tasks import send_register_active_email
from django.contrib.auth import authenticate, login, logout
from utils.mixin import LoginRequiredMixin
from django_redis import get_redis_connection
from apps.goods.models import GoodsSKU


# /user/register
def register(request):
    '''显示注册页面'''
    if request.method == 'GET':
        return render(request, 'register.html')
    else:
        '''进行注册处理'''

        # 接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 进行数据校验
        if not all([username, password, email]):
            # 数据不完整
            print('--> error in data validate')
            return render(request, 'register.html', {'errormsg': '数据不完整'})

        # 校验邮箱
        if not re.match('^[a-zA-Z0-9_-]+@[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+)+$', email):
            print('--> error in email')
            return render(request, 'register.html', {'errormsg': '邮箱格式错误'})
        # 是否同意协议
        if allow != 'on':
            print('--> error in allow')
            return render(request, 'register.html', {'errormsg': '请先同意协议'})
        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None
        if user:
            return render(request, 'register.html', {'errormsg': '用户名已存在'})

        # 进行业务处理：进行用户注册
        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_active = 0  # 用户还没激活
        user.save()

        # 返回应答,跳转到首页
        return redirect(reverse('goods:index'))


# /user/register
class RegisterView(View):
    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        '''进行注册处理'''

        # 接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 进行数据校验
        if not all([username, password, email]):
            # 数据不完整
            print('--> error in data validate')
            return render(request, 'register.html', {'errormsg': '数据不完整'})

        # 校验邮箱
        if not re.match('^[a-zA-Z0-9_-]+@[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+)+$', email):
            print('--> error in email')
            return render(request, 'register.html', {'errormsg': '邮箱格式错误'})
        # 是否同意协议
        if allow != 'on':
            print('--> error in allow')
            return render(request, 'register.html', {'errormsg': '请先同意协议'})
        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None
        if user:
            return render(request, 'register.html', {'errormsg': '用户名已存在'})

        # 进行业务处理：进行用户注册
        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_active = 0  # 用户还没激活
        user.save()

        # 发送激活右键，包含激活链接：
        # 激活连接中需要包含用户的身份信息,且加密信息

        # 加密用户的身份信息，生成激活token
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info)
        token = token.decode()

        # 发送邮件
        send_register_active_email.delay(email, username, token)

        # 返回应答,跳转到首页
        return redirect(reverse('goods:index'))


# /user/active/token...
class ActiveView(View):
    '''用户激活'''

    def get(self, request, token):
        '''进行用户激活'''
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            # 获取待激活的用户id
            user_id = info['confirm']
            # 根据id获取用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            # 跳转到登录页面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            # 激活链接已过期
            return HttpResponse('激活链接已过期')


# /user/login
class LoginView(View):
    '''登录页面'''

    def get(self, request):
        '''显示登录页面'''
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request, 'login.html', {'username': username, 'checked': checked})

    def post(self, request):
        '''登录校验'''

        # 接收数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        remember = request.POST.get('remember')
        # 校验数据
        if not all([username, password]):
            return render(request, 'login.html', {'errormsg': '数据不完整'})
        # 业务处理：登录校验
        user = authenticate(username=username, password=password)
        if user is not None:
            # 用户名密码正确
            if user.is_active:
                # 用户已经激活
                # 记录用户的登录状态
                login(request, user)

                # 由于login页面没有设置action的时候，会向地址栏中的地址提交数据，所以先获取登录后所要跳转的地址
                # eg:http://127.0.0.1:8000/user/login/?next=/user/
                # 如果没有next参数，则默认跳转到首页
                next_url = request.GET.get('next', reverse('goods:index'))
                # 跳转到next_url
                response = redirect(next_url)  # HttpResponseRedirect

                # 判断是否需要记住用户名
                if remember == 'on':
                    response.set_cookie('username', username, max_age=7 * 24 * 3600)
                else:
                    response.delete_cookie('username')
                return response

            else:
                return render(request, 'login.html', {'errormsg': '账户尚未激活'})
        else:
            # 用户名密码不正确
            return render(request, 'login.html', {'errormsg': '用户名或者密码错误'})
        # 返回应答


# /user/logout
class LogoutView(View):
    '''退出登录'''

    def get(self, request):
        # 清除用户的session信息
        logout(request)

        # 跳转到首页
        return redirect(reverse('goods:index'))


# /user
class UserInfoView(LoginRequiredMixin, View):
    '''用户中心-信息页'''

    def get(self, request):
        # page参数用于动态设置 base_user_center中的 class 为 active
        # request.user.is_authenticated()
        # 如果用户未登录 -> AnonymousUser类的一个实例
        # 登录时User类的一个实例
        # 除了自定义给模板传递的变量外，django会把request.user也传递的

        # 获取用户的个人信息
        user = request.user
        address = Address.objects.get_default_address(user=user)
        # 获取用户的历史浏览记录
        con = get_redis_connection('default')
        history_key = 'history_%d' % user.id

        # 获取最新浏览的5个商品的id
        sku_ids = con.lrange(history_key, 0, 4)
        # 从数据库中查询用户浏览的商品的具体信息
        # goods_li = GoodsSKU.objects.filter(id__in=sku_ids)
        #
        # goods_res = []
        # for sku_id in sku_ids:
        #     for goods in goods_li:
        #         if sku_id == goods:
        #             goods_res.append(goods)

        # 遍历获取用户浏览的商品信息
        goods_li = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_li.append(goods)

        context = {
            'page': 'user',
            'address': address,
            'goods_li': goods_li,
        }
        return render(request, 'user_center_info.html', context)


# /user/order
class UserOrderView(LoginRequiredMixin, View):
    '''用户中心-订单页'''

    def get(self, request, page):
        # page参数用于动态设置 base_user_center中的 class 为 active

        # 获取用户的订单信息
        user = request.user
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')

        # 遍历获取订单商品的信息
        for order in orders:
            order_skus = OrderGoods.objects.filter(order_info=order.id)

            # 遍历order_skus计算商品的小计
            for order_sku in order_skus:
                amount = int(order_sku.count) * order_sku.price
                # 动态绑定小计
                order_sku.amount = amount
            # 保存订单的支付状态
            order.status_name = OrderInfo.ORDER_STATUS_DIC[order.order_status]
            # 动态给order增加属性，保存商品信息
            order.order_skus = order_skus
        # 分页
        paginator = Paginator(orders, 5)
        # 判断page是否超过范围
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的Page实例对象
        order_page = paginator.page(page)

        # 进行页码的控制，页面最多显示5个页码
        num_pages = paginator.num_pages
        # 1.如果小于5页，页面上显示所有页码
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        # 2.如果当前页是前3页，显示1-5页
        elif page <= 3:
            pages = range(1, 6)
        # 3.如果当前页是后3页，显示后5页
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        # 4.其他情况，显示当前页的前2页/当前页/当前页的后2页
        else:
            pages = range(page - 2, page + 3)

        # 组织上下文
        context = {
            'order_page': order_page,
            'pages': pages,
            'page': 'order'

        }

        return render(request, 'user_center_order.html', context)


# /user/address
class AddressView(LoginRequiredMixin, View):
    '''用户中心-地址页'''

    def get(self, request):
        # page参数用于动态设置 base_user_center中的 class 为 active

        user = request.user
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     # 不存在收货地址
        #     address = None
        address = Address.objects.get_default_address(user)

        # 获取用户的默认收货地址
        return render(request, 'user_center_site.html', {'page': 'address', 'address': address})

    def post(self, request):
        '''地址的添加'''

        # 接收数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('address')
        zipcode = request.POST.get('zipcode')
        phone = request.POST.get('phone')
        # 校验数据
        if not all([receiver, addr, phone]):
            return render(request, 'user_center_site.html', {'errormsg': '数据不完整'})

        # 校验手机号
        if not re.match('^1(3|4|5|7|8)\d{9}$', phone):
            return render(request, 'user_center_site.html', {'errormsg': '手机号格式不正确'})
        # 业务处理：地址的添加
        # 如果已经存在默认收货地址，则添加的地址不作为默认地址
        # 获取登录用户的对应User对象
        user = request.user
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     # 不存在收货地址
        #     address = None
        address = Address.objects.get_default_address(user)

        if address:
            is_default = False
        else:
            is_default = True
        print(address)
        Address.objects.create(user=user, receiver=receiver, addr=addr, zip_code=zipcode, phone=phone,
                               is_default=is_default)

        # 返回应答:刷新地址页面
        return redirect(reverse('user:address'))
