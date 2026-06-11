from django.urls import re_path

from committee_web.consumers import RunConsumer

websocket_urlpatterns = [
    re_path(r"^ws/run/(?P<market>[^/]+)/(?P<stock_no>[^/]+)$", RunConsumer.as_asgi()),
]
