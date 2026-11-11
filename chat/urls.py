from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("widget.js", views.widget_js, name="widget_js"),
    path("healthz", views.healthz, name="healthz"),
    path("api/sites/<slug:slug>/config", views.site_config, name="site_config"),
    path("api/sites/<slug:slug>/messages", views.messages, name="messages"),
    path("api/conversations/<uuid:pk>", views.conversation_detail, name="conversation_detail"),
]
