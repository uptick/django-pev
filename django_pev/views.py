from typing import Any

from django.shortcuts import render
from django.views.generic import TemplateView

from .utils import indexes, maintenance, space

# Create your views here.


def index(request):
    return render(request, "django_pev/index.html")


class SpaceView(TemplateView):
    template_name = "django_pev/space.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)

        ctx["database_size"] = space.get_database_size()
        ctx["tables"] = space.get_table_sizes()
        # ctx['indexes'] = indexes.get_indexes()
        ctx["indexes"] = space.get_index_sizes()

        ctx["indexes_size"] = sum(c.size_bytes for c in ctx["indexes"])
        ctx["table_size"] = sum(c.size_bytes for c in ctx["tables"])

        return ctx


class MaintenanceView(TemplateView):
    template_name = "django_pev/maintenance.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)

        ctx["tables"] = maintenance.get_maintenance_info()
        return ctx


class IndexesView(TemplateView):
    template_name = "django_pev/indexes_view.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        all_indexes = indexes.get_indexes()
        ctx["all_indexes"] = all_indexes
        ctx["unused_indexes"] = sorted(
            [i for i in all_indexes if i.is_unused], key=lambda i: i.size_bytes, reverse=True
        )
        ctx["duplicated_indexes"] = sorted(
            [i for i in all_indexes if i.is_duplicated], key=lambda i: i.size_bytes, reverse=True
        )

        ctx.update(indexes.get_index_stats())
        return ctx
