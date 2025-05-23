import logging
import uuid
from contextlib import suppress
from typing import Any

from django import forms
from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.cache import cache
from django.http import HttpRequest, HttpResponseRedirect
from django.http.response import HttpResponse as HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.module_loading import import_string
from django.views.generic import FormView, TemplateView

from .utils import ExplainSet, explain, indexes, live_connections, maintenance, queries, space

logger = logging.getLogger(__name__)


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
    url = forms.CharField(required=True)
    http_method = forms.ChoiceField(
        choices=[("GET", "GET"), ("POST", "POST"), ("PATCH", "PATCH"), ("PUT", "PUT"), ("DELETE", "DELETE")],
        initial="GET",
    )
    body = forms.CharField(required=False)


class ExplainView(FormView, BaseView):
    """List view of queries resulting from an explain request on a url"""

    template_name = "django_pev/explain.html"
    form_class = ExplainForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.method == "GET":
            # Pre-populate form with GET parameters
            kwargs["data"] = self.request.GET
        return kwargs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        form = kwargs.get("form") or self.get_form()
        explain_result = None

        if form.is_valid():
            TestClient = import_string(getattr(settings, "DJANGO_PEV_EXPLAIN_TEST_CLIENT", "django.test.Client"))
            ctx["url"] = url = form.cleaned_data["url"]
            ctx["http_method"] = http_method = form.cleaned_data["http_method"]
            ctx["body"] = body = form.cleaned_data["body"]

            client = TestClient()
            client.force_login(self.request.user)  # type:ignore

            with explain(url=url) as e:
                try:
                    match http_method:
                        case "GET" | "DELETE":
                            resp = client.generic(http_method, url, follow=True)
                        case "POST" | "PUT" | "PATCH":
                            resp = client.generic(
                                http_method, url, data=body, content_type="application/json", follow=True
                            )
                    ctx["resp_status_code"] = resp.status_code
                    if resp.status_code >= 400:
                        with suppress(Exception):
                            resp_json = resp.json()
                            ctx["error"] = resp_json
                except Exception as exc:
                    logger.error(f"Error fetching {url}")
                    ctx["error"] = str(exc)
            explain_result = e

        ctx["explain"] = explain_result
        ctx["nplusones"] = explain_result.nplusones if explain_result else {}

        if explain_result and explain_result.queries:
            cache.set(
                get_cache_key(explain_result.id),
                explain_result,
                timeout=getattr(settings, "DJANGO_PEV_CACHE_TIMEOUT", 60 * 60 * 24),
            )
            ctx["slowest"] = explain_result.slowest

        return ctx


class AnalyzeForm(forms.Form):
    explainset_id = forms.CharField()
    query_index = forms.CharField()
    analyze = forms.BooleanField(required=False)


class ExplainVisualize(FormView, BaseView):
    template_name = "django_pev/pev_embedded.html"
    form_class = AnalyzeForm

    def form_valid(self, form: AnalyzeForm):
        explain_set = cache.get(get_cache_key(form.cleaned_data["explainset_id"]), None)
        if not explain_set:
            return HttpResponseRedirect(reverse("django_pev:explain"))

        assert isinstance(explain_set, ExplainSet)

        query = explain_set.queries[int(form.cleaned_data["query_index"])]
        is_analyze = bool(form.cleaned_data["analyze"])
        explain_plan = query.explain(analyze=is_analyze)
        explain_id = str(uuid.uuid4())

        context = {
            "explain_id": explain_id,
            "explain_set": explain_set,
            "plan": explain_plan,
            "query": query,
            "optimization_prompt": query.optimization_prompt(analyze=is_analyze),
        }

        cache.set(
            get_cache_key(explain_id),
            context,
            timeout=getattr(settings, "DJANGO_PEV_CACHE_TIMEOUT", 60 * 60 * 24),
        )

        return HttpResponseRedirect(f"{reverse('django_pev:embedded-pev')}?explain_id={explain_id}")


class EmbeddedPev(BaseView):
    template_name = "django_pev/pev_embedded.html"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not self.request.GET.get("explain_id"):
            return HttpResponseRedirect(f"{reverse('django_pev:explain')}")

        explain_id = self.request.GET["explain_id"]

        explain_plan = cache.get(get_cache_key(explain_id), None)
        if not explain_plan:
            return HttpResponseRedirect(f"{reverse('django_pev:explain')}")

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        explain_context: dict = cache.get(get_cache_key(self.request.GET["explain_id"]))
        ctx["query"] = explain_context["query"].sql
        ctx["plan"] = explain_context["plan"]
        ctx["url"] = explain_context["explain_set"].url
        ctx["duration"] = explain_context["query"].duration
        ctx["ai_prompt"] = explain_context["optimization_prompt"]

        return ctx
