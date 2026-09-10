from django.urls import path
from . import views

app_name = 'worlds'

urlpatterns = [
    path('health/', views.health, name='health'),
    path('generate/', views.generate_world, name='generate'),
    path('generate/file/', views.generate_world_file, name='generate_file'),
]