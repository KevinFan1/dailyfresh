from django.urls import path, include
from . import views

app_name = 'order'
urlpatterns = [
    path('place/', views.OrderPlaceView.as_view(), name='place'),  # 订单页面
    path('commit/', views.OrderCommitView.as_view(), name='commit'),  # 订单提交
    path('pay/', views.OrderPayView.as_view(), name='pay'),  # 支付
    path('check/', views.CheckPayView.as_view(), name='check'),  # 支付
    path('comment/<int:order_id>/', views.CommentView.as_view(), name='comment'),  # 支付
]
