from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name="index"),
    path('space', views.SpaceView.as_view(), name="space"),
    path('maintenance', views.MaintenanceView.as_view(), name="maintenance"),
    path('connections', views.ConnectionsView.as_view(), name="connections"),
    path('indexes', views.IndexesView.as_view(), name="indexes"),
    path('queries', views.IndexesView.as_view(), name="queries"),
    path('live-queries', views.IndexesView.as_view(), name="live-queries"),
]
