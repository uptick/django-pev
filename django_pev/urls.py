from django.urls import path

from . import views

urlpatterns = [
    path("", views.QueriesView.as_view(), name="index"),
    path("space", views.SpaceView.as_view(), name="space"),
    path("maintenance", views.MaintenanceView.as_view(), name="maintenance"),
    path("connections", views.ConnectionsView.as_view(), name="connections"),
    path("indexes", views.IndexesView.as_view(), name="indexes"),
    path("live-queries", views.LiveQueriesView.as_view(), name="live-queries"),
    path("queries", views.QueriesView.as_view(), name="queries"),
    path("explain", views.ExplainView.as_view(), name="explain"),
    path("explain-visualize", views.ExplainVisualize.as_view(), name="explain-visualize"),
    path("embedded-pev", views.EmbeddedPev.as_view(), name="embedded-pev"),
]
