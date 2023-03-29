from django.contrib import admin
from django.urls import path
from firebase_app import views
from django.views.static import serve
from django.urls import re_path
from .settings import *

urlpatterns = [
	path('admin/', admin.site.urls),
    path('', views.home),
    path('emotion/', views.chat_emotion),
    path("fun/", views.chat_fun),
    path("save/", views.save_conversation),
    path("image/", views.image_generate),
    path("download/", views.download_image),
    # re_path(r'^media/(?P<path>.*)$', serve, {'document_root': MEDIA_ROOT}),
]
