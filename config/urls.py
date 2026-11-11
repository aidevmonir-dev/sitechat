from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "SiteChat"
admin.site.site_title = "SiteChat"
admin.site.index_title = "Sites, help articles and conversations"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("chat.urls")),
]
