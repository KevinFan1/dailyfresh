# 使用celery
import os

from celery import Celery
from django.conf import settings
from django.template import loader

from apps.goods.models import GoodsType, GoodsBanner, GoodsPromotion, GoodsTypeShow
from django.core.mail import send_mail

# 创建一个Celery对象
app = Celery('celery_task', broker='redis://127.0.0.1:6379/8')


# 定义任务函数
@app.task
def send_register_active_email(to_email, username, token):
    # 发送邮件
    subject = 'DailyFresh Register Email'
    message = ''
    sender = settings.EMAIL_FROM
    reveicer = [to_email]
    html_body = '<h1>尊敬的用户 %s, 感谢您注册天天生鲜！</h1>' \
                '<br/><p>请点击此链接激活您的帐号<a href="http://127.0.0.1:8000/user/active/%s">' \
                'http://127.0.0.1:8000/user/active/%s<a></p>' % (username, token, token)
    send_mail(subject, message, sender, reveicer, html_message=html_body)


@app.task
def generate_static_index_html():
    '''产生首页静态页面'''
    # 获取商品的种类信息
    types = GoodsType.objects.all()
    # 获取首页轮播商品信息
    goods_banners = GoodsBanner.objects.all().order_by('index')  # 0 1 2 3
    # 获取首页促销活动信息
    promotion_banners = GoodsPromotion.objects.all().order_by('index')
    # 获取首页分类商品展示信息
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

    # 使用模板
    # 1.加载模板文件
    temp = loader.get_template('static_index.html')
    # 2.渲染模板
    static_index_html = temp.render(context)
    print(static_index_html)
    # 生成首页对应静态文件
    save_path = os.path.join(settings.BASE_DIR, 'static/index.html')
    with open(save_path, 'w', encoding='utf-8') as f:
        f.write(static_index_html)
