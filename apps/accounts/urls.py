from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('account/register/', views.register, name='register'),
    path('account/login/', views.login_view, name='login'),
    path('account/logout/', views.logout_view, name='logout'),
    path('account/password/', views.change_password, name='change_password'),
    path('profile/', views.profile, name='profile'),
    path('profile/preferences/', views.preferences, name='preferences'),
    path('profile/delete/', views.delete_account, name='delete_account'),
    path('profile/export/', views.export_data, name='export_data'),
]