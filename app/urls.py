from django.urls import path
from . import views

app_name = 'app'

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard_page, name='dashboard_page'),
    path('upload/files/', views.handle_multiple_uploads, name='handle_multiple_uploads'),
] 