from django.db import models
from db.base_model import BaseModel
from tinymce.models import HTMLField


class Goods(BaseModel):
    '''商品SPU模型类'''
    name = models.CharField(max_length=20, verbose_name='商品SPU名称')
    detail = HTMLField(blank=True, verbose_name='商品详情')

    class Meta:
        db_table = 'df_goods'
        verbose_name = '商品SPU'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class GoodsType(BaseModel):
    '''商品类型类'''
    name = models.CharField(max_length=20, verbose_name='分类名称')
    logo = models.CharField(max_length=10, verbose_name='标识')
    image = models.ImageField(upload_to='type', verbose_name='商品类型图片')

    class Meta:
        db_table = 'df_goods_type'
        verbose_name = '商品分类'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class GoodsSKU(BaseModel):
    GOODS_STATUS = (
        (0, '下线'),
        (1, '上线')
    )
    name = models.CharField(max_length=50, verbose_name='商品名称')
    desc = models.CharField(max_length=100, verbose_name='商品简介')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='商品价格')
    unite = models.CharField(max_length=20, verbose_name='单位')
    image = models.ImageField(upload_to='goods', verbose_name='商品图片')
    inventory = models.IntegerField(default=1, verbose_name='库存')
    sales = models.IntegerField(default=0, verbose_name='销量')
    status = models.SmallIntegerField(default=1, choices=GOODS_STATUS, verbose_name='商品状态')
    type = models.ForeignKey('GoodsType', on_delete=models.CASCADE, verbose_name='所属分类')
    goods = models.ForeignKey('Goods', on_delete=models.CASCADE, verbose_name='商品SPU')

    class Meta:
        db_table = 'df_goods_sku'
        verbose_name = '商品'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class GoodImage(BaseModel):
    image = models.ImageField(upload_to='goods', verbose_name='商品图片路径')
    goods = models.ForeignKey('GoodsSKU', on_delete=models.CASCADE, verbose_name='商品')

    class Meta:
        db_table = 'df_goods_image'
        verbose_name = '商品图片'
        verbose_name_plural = verbose_name


class GoodsBanner(BaseModel):
    image = models.ImageField(upload_to='banner', verbose_name='轮播图片')
    index = models.SmallIntegerField(default=0, verbose_name='轮播索引')
    goods = models.ForeignKey('GoodsSKU', on_delete=models.CASCADE, verbose_name='商品')

    class Meta:
        db_table = 'df_goods_banner'
        verbose_name = '首页轮播商品'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.goods.name


class GoodsPromotion(BaseModel):
    '''促销模型类'''
    name = models.CharField(max_length=20, verbose_name='活动名称')
    image = models.ImageField(upload_to='banner', verbose_name='活动图片')
    url = models.CharField(max_length=256, verbose_name='互动连接')
    index = models.SmallIntegerField(default=0, verbose_name='展示顺序')

    class Meta:
        db_table = 'df_goods_promotion'
        verbose_name = '促销活动'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class GoodsTypeShow(BaseModel):
    DISPLAY_TYPE_CHOICES = (
        (0, '文字'),
        (1, '图片')
    )
    display_type = models.SmallIntegerField(choices=DISPLAY_TYPE_CHOICES, default=1, verbose_name='展示类型')
    index = models.SmallIntegerField(default=0, verbose_name='展示顺序')
    sku = models.ForeignKey('GoodsSKU', on_delete=models.CASCADE, verbose_name='商品SKU')
    goods_type = models.ForeignKey('GoodsType', on_delete=models.CASCADE, verbose_name='商品种类')

    class Meta:
        db_table = 'df_goods_show'
        verbose_name = '分类商品展示'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.sku.name
