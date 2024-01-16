from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name="index"),
    path('space', views.SpaceView.as_view(), name="space"),
    path('maintenance', views.MaintenanceView.as_view(), name="maintenance"),
    path('indexes', views.IndexesView.as_view(), name="indexes")
]
