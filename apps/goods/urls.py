from django.urls import path, include
from . import views

app_name = 'goods'
urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),  # 首页
    path('goods/<int:goods_id>/', views.DetailView.as_view(), name='detail'),  # 详情页
    path('list/<int:type_id>/<int:page>/', views.ListView.as_view(), name='list'),  # 商品列表页
]
