from django.urls import path, include
from . import views

app_name = 'cart'
urlpatterns = [
    path('add/', views.CartAddView.as_view(), name='add'),  # 购物车记录添加
    path('update/', views.CartUpdateView.as_view(), name='update'),  # 购物车记录更新
    path('delete/', views.CartDeleteView.as_view(), name='delete'),  # 购物车记录删除
    path('', views.CartInfoView.as_view(), name='show'),  # 购物车信息页面
]
