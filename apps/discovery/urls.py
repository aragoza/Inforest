from django.urls import path
from . import views

app_name = 'discovery'

urlpatterns = [
    path('', views.discovery_list, name='list'),
    path('<int:pk>/', views.discovery_detail, name='detail'),
]