import functools
import logging
import traceback
import webbrowser
from contextlib import contextmanager
from dataclasses import dataclass, field

from django.core.signals import request_started
from django.db import connections, reset_queries

from django_pev.dalibo import PevResponse, upload_sql_plan
from django_pev.exceptions import PevException

logger = logging.Logger("django_pev")


@dataclass(frozen=True)
class Explain:
    index: int
    duration: float
    sql: str
    stack_trace: str
    db_alias: str

    def __repr__(self) -> str:
        return f"Explain(duration={self.duration} sql={self.sql[:20]})"

    def __str__(self) -> str:
        return f"Explain(duration={self.duration} sql={self.sql[:20]})"

    @functools.cache  # noqa
    def visualize(self, upload_query: bool = False, analyze: bool = True, title: str = "") -> PevResponse:
        """Uploads the query and plan to explain.dalibo

        By default we do not embed the SQL query unless `upload_query` is set to True.

        The PevResponse object can be used to delete the uploaded plan.
        """
        with connections[self.db_alias].cursor() as cursor:
            if analyze:
                sql = f"EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON) {self.sql}"
            else:
                sql = f"EXPLAIN (VERBOSE, FORMAT JSON) {self.sql}"
            cursor.execute(sql)
            plan = cursor.fetchone()[0]
        response = upload_sql_plan(query=self.sql if upload_query else "", plan=plan, title=title)
        logging.info(f"View Postgresql Explain @ {response.url}")
        return response

    def visualize_in_browser(self, upload_query: bool = False, analyze: bool = True, title: str = "") -> PevResponse:
        """Uploads the query and plan t oexplain.dalibo and then open in the browser"""
        response = self.visualize(upload_query, analyze, title)
        webbrowser.open(response.url)
        return response

    def explain(self, analyze: bool = True) -> str:
        with connections[self.db_alias].cursor() as cursor:
            if analyze:
                sql = f"EXPLAIN ANALYZE {self.sql}"
            else:
                sql = f"EXPLAIN {self.sql}"
            cursor.execute(sql)
            explain = cursor.fetchone()[0]
        return explain


@dataclass
class ExplainSet:
    queries: list[Explain] = field(default_factory=list)

    @property
    def n_queries(self) -> int:
        return len(self.queries)

    def __getitem__(self, index: int) -> Explain:
        return self.queries[index]

    @property
    def slowest(self) -> Explain:
        if not self.queries:
            raise PevException("Can not visualize results when there are no results.")

        return sorted(self.queries, key=lambda q: q.duration, reverse=True)[0]


@contextmanager
def explain(
    db_alias: str = "default",
    trace_limit: int = 10,
):
    """Capture all queries within this context and returns an ExplainSet container.

    Captured queries contain timing information, a stack trace and allows for visualization
    with explain.dalibo.com

    Usage:
    >>> with explain() as queries:
    >>>    User.objects.count()
    >>> result = queries.slowest.visualize(upload_query=True)
    >>> result.delete()
    >>> queries.slowest.explain()
    """
    result = ExplainSet()
    conn = connections[db_alias]

    force_debug_cursor = conn.force_debug_cursor
    conn.force_debug_cursor = True
    request_started.disconnect(reset_queries)

    logger.debug("Reseting queries")
    reset_queries()
    try:
        yield result
    finally:
        conn.force_debug_cursor = force_debug_cursor
        request_started.connect(reset_queries)
    queries_after = conn.queries[:]
    logger.debug(f"Captured {len(queries_after)} queries")

    for index, q in enumerate(queries_after):
        result.queries.append(
            Explain(
                index=index,
                duration=float(q["time"]),
                sql=q["sql"],
                stack_trace="".join(traceback.format_stack()[-trace_limit:-2]),
                db_alias=db_alias,
            )
        )
