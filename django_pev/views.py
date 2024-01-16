from typing import Any

from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import render
from django.views.generic import TemplateView

from .utils import indexes, live_connections, maintenance, queries, space

# Create your views here.


def index(request):
    return render(request, "django_pev/index.html")


class BaseView(UserPassesTestMixin, TemplateView):
    template_name = "django_pev/indexes_view.html"

    def test_func(self):
        return self.request.user.is_superuser


class SpaceView(BaseView):
    template_name = "django_pev/space.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)

        ctx["database_size"] = space.get_database_size()
        ctx["tables"] = space.get_table_sizes()
        ctx["indexes"] = space.get_index_sizes()

        ctx["indexes_size"] = sum(c.size_bytes for c in ctx["indexes"])
        ctx["table_size"] = sum(c.size_bytes for c in ctx["tables"])

        return ctx


class MaintenanceView(BaseView):
    template_name = "django_pev/maintenance.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)

        ctx["tables"] = maintenance.get_maintenance_info()
        return ctx


class IndexesView(BaseView):
    template_name = "django_pev/indexes_view.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        all_indexes = indexes.get_indexes()
        ctx["all_indexes"] = all_indexes
        ctx["unused_indexes"] = sorted(
            [i for i in all_indexes if i.is_unused],
            key=lambda i: i.size_bytes,
            reverse=True,
        )
        ctx["duplicated_indexes"] = sorted(
            [i for i in all_indexes if i.is_duplicated],
            key=lambda i: i.size_bytes,
            reverse=True,
        )

        ctx.update(indexes.get_index_stats())
        return ctx


class ConnectionsView(BaseView):
    template_name = "django_pev/connections.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["connections"] = live_connections.get_connections_current_database()
        return ctx


class LiveQueriesView(BaseView):
    template_name = "django_pev/live_queries.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["queries"] = queries.get_live_queries_current_database()
        return ctx


class QueriesView(BaseView):
    template_name = "django_pev/queries.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["queries"] = queries.get_query_stats()
        ctx["is_pg_stats_enabled"] = queries.is_pg_stat_statements_installed()
        ctx["queries_by_io"] = sorted(queries.get_query_stats(), key=lambda i: i.shared_blks_hit, reverse=True)
        ctx["queries_by_slowest"] = sorted(queries.get_query_stats(), key=lambda i: i.mean_time, reverse=True)
        return ctx
