import uuid
from typing import Any

from django import forms
from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.cache import cache
from django.http import HttpRequest, HttpResponseRedirect
from django.http.response import HttpResponse as HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import FormView, TemplateView

from .utils import ExplainSet, explain, indexes, live_connections, maintenance, queries, space

# Create your views here.


def get_cache_key(explainset_id: Any) -> str:
    return f"DJANGO_PEV:EXPLAIN:{explainset_id}"


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


class ExplainForm(forms.Form):
    url = forms.CharField(help_text="The URL to explain eg: /dashboard/")

    def send_email(self):
        # send email using the self.cleaned_data dictionary
        pass


class ExplainView(FormView, BaseView):
    template_name = "django_pev/explain.html"
    form_class = ExplainForm

    def form_valid(self, form: ExplainForm):
        url = form.cleaned_data["url"]
        from django.test import Client as TestClient

        client = TestClient()
        # Authentication

        client.force_login(self.request.user)  # type:ignore

        # Overriding settings

        with explain(url=url) as e:
            client.get(url, follow=True)

        return self.render_to_response(self.get_context_data(form=form, explain=e))

    def get_context_data(self, form=None, explain: ExplainSet | None = None, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)

        ctx["explain"] = explain
        if form:
            ctx["url"] = form.cleaned_data["url"]
        if explain and explain.queries:
            cache.set(
                get_cache_key(explain.id),
                explain,
                timeout=getattr(settings, "DJANGO_PEV_CACHE_TIMEOUT", 60 * 60 * 24),
            )
            ctx["slowest"] = explain.slowest

        return ctx


class AnalyzeForm(forms.Form):
    explainset_id = forms.CharField()
    query_index = forms.CharField()

    def send_email(self):
        # send email using the self.cleaned_data dictionary
        pass


class ExplainVisualize(FormView, BaseView):
    template_name = "django_pev/pev_embedded.html"
    form_class = AnalyzeForm

    def form_valid(self, form: AnalyzeForm):
        explain_set = cache.get(get_cache_key(form.cleaned_data["explainset_id"]), None)
        if not explain_set:
            return HttpResponseRedirect(reverse("django_pev:explain"))

        assert isinstance(explain_set, ExplainSet)

        query = explain_set.queries[int(form.cleaned_data["query_index"])]
        explain_plan = query.explain()
        explain_id = str(uuid.uuid4())

        context = {
            "explain_id": explain_id,
            "explain_set": explain_set,
            "plan": explain_plan,
            "query": query.sql,
        }

        cache.set(
            get_cache_key(explain_id),
            context,
            timeout=getattr(settings, "DJANGO_PEV_CACHE_TIMEOUT", 60 * 60 * 24),
        )

        return HttpResponseRedirect(f'{reverse("django_pev:embedded-pev")}?explain_id={explain_id}')


class EmbeddedPev(BaseView):
    template_name = "django_pev/pev_embedded.html"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not self.request.GET.get("explain_id"):
            return HttpResponseRedirect(f'{reverse("django_pev:explain")}')

        explain_id = self.request.GET["explain_id"]

        explain_plan = cache.get(get_cache_key(explain_id), None)
        if not explain_plan:
            return HttpResponseRedirect(f'{reverse("django_pev:explain")}')

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        explain_context: dict = cache.get(get_cache_key(self.request.GET["explain_id"]))
        ctx["query"] = explain_context["query"]
        ctx["plan"] = explain_context["plan"]

        return ctx
