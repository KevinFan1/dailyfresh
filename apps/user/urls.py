from django.urls import path
from . import views
from django.contrib.auth.decorators import login_required

app_name = 'user'
urlpatterns = [
    # path('register/',views.register,name='register'),
    path('register/', views.RegisterView.as_view(), name='register'),  # 注册页面

    path('login/', views.LoginView.as_view(), name='login'),  # 登录页面
    path('logout/', views.LogoutView.as_view(), name='logout'),  # 退出登录

    path('active/<token>', views.ActiveView.as_view(), name='active'),  # 用户激活

    path('', views.UserInfoView.as_view(), name='user'),  # 用户中心信息页面
    path('order/<int:page>', views.UserOrderView.as_view(), name='order'),  # 用户中心订单页面
    path('address/', views.AddressView.as_view(), name='address'),  # 用户中心地址页面

]
