from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/worlds/generate/', consumers.WorldConsumer.as_asgi()),
]