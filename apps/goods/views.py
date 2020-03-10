from django.core.cache import cache
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, reverse
from django.views.generic import View
from .models import GoodsType, GoodsBanner, GoodsPromotion, GoodsTypeShow, GoodsSKU
from django_redis import get_redis_connection
from apps.order.models import OrderGoods


# 127.0.0.1:8000
class IndexView(View):
    '''首页'''

    def get(self, request):
        # 查询时候已经有缓存
        context = cache.get('index_page_data')

        if context is None:
            '''设置缓存'''
            print('设置缓存')
            # 获取商品的种类信息
            types = GoodsType.objects.all()

            # 获取首页轮播商品信息
            goods_banners = GoodsBanner.objects.all().order_by('index')  # 0 1 2 3
            # 获取首页促销活动信息
            promotion_banners = GoodsPromotion.objects.all().order_by('index')
            # 获取首页分类商品展示信息
            image = []
            for type in types:
                # 获取type种类首页分页商品的图片信息
                image_banners = GoodsTypeShow.objects.filter(goods_type=type, display_type=1).order_by('index')
                # 获取type种类首页分页商品的文字信息
                title_banners = GoodsTypeShow.objects.filter(goods_type=type, display_type=0).order_by('index')
                # 动态给type增加属性，分别保存首页分类商品的图片和文字信息

                type.image_banners = image_banners
                type.title_banners = title_banners

            context = {'types': types,
                       'goods_banners': goods_banners,
                       'promotion_banners': promotion_banners,

                       }
            # 设置缓存
            cache.set('index_page_data', context, 3600)

        # 获取用户购物车中商品的数目
        cart_count = 0
        # 先验证是否用户已经登录，登录再获取购物车的数目
        user = request.user
        if user.is_authenticated:
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

        # 把购物车数目添加到context
        context.update(cart_count=cart_count)

        return render(request, 'index.html', context)


# /goods/goods_id
class DetailView(View):
    '''详情页'''

    def get(self, request, goods_id):
        '''显示详情页面'''
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在
            return redirect(reverse('goods:index'))

        # 获取商品得分类信息
        types = GoodsType.objects.all()
        # 获取商品的评论信息,排除空的评论
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')
        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]

        # 获取同一个SPU的其他规格商品, exclude排除自身
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)

        # 获取用户购物车中商品的数目
        cart_count = 0
        # 先验证是否用户已经登录，登录再获取购物车的数目
        user = request.user
        if user.is_authenticated:
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

            # 添加用户历史浏览记录
            conn = get_redis_connection('default')
            history_key = 'history_%d' % user.id
            # 移除列表中的goods_id
            conn.lrem(history_key, 0, goods_id)
            # 把goods_id插入列表左边
            conn.lpush(history_key, goods_id)
            # 只保存用户最新浏览的5条信息
            conn.ltrim(history_key, 0, 4)

        # 组织需要传递的数据
        context = {
            'sku': sku,
            'types': types,
            'sku_orders': sku_orders,
            'new_skus': new_skus,
            'cart_count': cart_count,
            'same_spu_skus': same_spu_skus,
        }

        return render(request, 'detail.html', context)


# 种类id,页码，排序方式
# /list/种类id/页码?sort=排序方式
class ListView(View):
    '''列表页面'''

    def get(self, request, type_id, page):
        '''显示列表页'''
        # 获取种类信息
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            return redirect(reverse('goods:index'))

        # 获取商品分类信息
        types = GoodsType.objects.all()
        # 获取排序的方式，sort=default 默认排序, sort=price 商品价格排序, sort=hot 商品排序
        sort = request.GET.get('sort')
        # 获取分类商品的信息
        skus = GoodsSKU.objects.filter(type=type)
        if sort == 'price':
            skus = skus.order_by('price')
        elif sort == 'hot':
            skus = skus.order_by('-sales')
        else:
            sort = 'default'
            skus = skus.order_by('-id')

        # 对数据进行分页
        paginator = Paginator(skus, 1)

        # 判断page是否超过范围
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的Page实例对象
        sku_page = paginator.page(page)

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

        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]

        # 获取用户购物车中商品的数目
        cart_count = 0
        # 先验证是否用户已经登录，登录再获取购物车的数目
        user = request.user
        if user.is_authenticated:
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

        context = {
            'type': type,
            'types': types,
            'sku_page': sku_page,
            'new_skus': new_skus,
            'cart_count': cart_count,
            'sort': sort,
            'pages': pages,
        }
        return render(request, 'list.html', context)
