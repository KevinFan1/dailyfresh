from django.contrib import admin
from apps.goods.models import GoodsType, GoodsPromotion, Goods, GoodsBanner, GoodsTypeShow,GoodsSKU
from celery_tasks.tasks import generate_static_index_html
from django.core.cache import cache


class BaseModelAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        '''新增或更新表中数据时调用'''
        super().save_model(request, obj, form, change)
        # 发出任务，让celery worker重新生成首页静态页面
        generate_static_index_html.delay()

        # 清除首页的缓存数据
        cache.delete('index_page_data')

    def delete_model(self, request, obj):
        '''删除表中数据时调用'''
        super().delete_model(request, obj)
        generate_static_index_html.delay()

        # 清除首页的缓存数据
        cache.delete('index_page_data')


class GoodsTypeAdmin(BaseModelAdmin):
    pass


class GoodsPromotionAdmin(BaseModelAdmin):
    pass


class GoodsBannerAdmin(BaseModelAdmin):
    pass


class GoodsTypeShowAdmin(BaseModelAdmin):
    pass
class GoodsAdmin(BaseModelAdmin):
    pass
class GoodsSKUAdmin(BaseModelAdmin):
    pass
admin.site.register(Goods, GoodsAdmin)
admin.site.register(GoodsSKU, GoodsSKUAdmin)
admin.site.register(GoodsType, GoodsTypeAdmin)
admin.site.register(GoodsPromotion, GoodsPromotionAdmin)
admin.site.register(GoodsBanner, GoodsBannerAdmin)
admin.site.register(GoodsTypeShow, GoodsTypeShowAdmin)
