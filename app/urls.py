from django.urls import path
from . import views

app_name = 'app'

urlpatterns = [
    path('', views.home, name='home'),
    path('upload/', views.upload_page, name='upload_page'),
] 