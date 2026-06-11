from django.conf import settings
from django.urls import path, re_path
from django.views.static import serve

from committee_web import views

urlpatterns = [
    path("", views.index),
    path("api/committee", views.committee_info),
    re_path(r"^reports/(?P<path>.*)$", serve, {"document_root": settings.REPORTS_DIR}),
]
