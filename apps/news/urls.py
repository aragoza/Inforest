from django.urls import path

from . import views

app_name = 'news'

urlpatterns = [
    path('', views.news_list, name='list'),
    path('favoris/', views.favorites, name='favorites'),
    path('historique/', views.history, name='history'),
    path('<uuid:pk>/', views.news_detail, name='detail'),
    path('<uuid:pk>/read/', views.news_read, name='read'),
    path('<uuid:pk>/favori/', views.toggle_favorite, name='toggle_favorite'),
]