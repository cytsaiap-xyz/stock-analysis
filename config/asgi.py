import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.staticfiles import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from committee_web.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": ASGIStaticFilesHandler(django_asgi_app),
    "websocket": URLRouter(websocket_urlpatterns),
})
