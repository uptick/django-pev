import datetime
import functools
import logging
import time
import traceback
import uuid
import webbrowser
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import local
from typing import Any

import sqlparse  # type:ignore[import]
from django.db import connections
from django.db.backends.utils import CursorWrapper
from django.utils import timezone

from django_pev.dalibo import PevResponse, upload_sql_plan
from django_pev.exceptions import PevException

logger = logging.Logger("django_pev")


thread_local_query_count = local()

CursorWrapper._original_execute = CursorWrapper._execute  # type:ignore
CursorWrapper._original_executemany = CursorWrapper._executemany  # type:ignore


@contextmanager
def record_sql(
    self: CursorWrapper,
    sql: str,
    params: Any,
):
    """Record the SQL query and parameters for use in the explain view"""
    thread_local_query_count.query_count = getattr(thread_local_query_count, "query_count", 0) + 1
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        thread_local_query_count.queries = getattr(thread_local_query_count, "queries", []) + [
            {"time": duration, "sql": self.cursor.mogrify(sql, params).decode("utf-8")}
        ]


def _new_execute(self, sql, params, *ignored_wrapper_args):  # type: ignore[no-untyped-def] # fmt: skip
    with record_sql(self, sql, params):
        return CursorWrapper._original_execute(self, sql, params, *ignored_wrapper_args)


def _new_executemany(self, sql, params, *ignored_wrapper_args):  # type: ignore[no-untyped-def] # fmt: skip
    with record_sql(sql, params):
        return CursorWrapper._original_executemany(self, sql, params, *ignored_wrapper_args)


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
        """Runs explain and returns the plan as a string"""
        with connections[self.db_alias].cursor() as cursor:
            if analyze:
                sql = f"EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS) {self.sql}"
            else:
                sql = f"EXPLAIN (VERBOSE) {self.sql}"
            cursor.execute(sql)
            plan = "\n".join(list(x[0] for x in cursor.fetchall()))
        return plan


@dataclass
class ExplainSet:
    id: str
    url: str
    created: datetime.datetime
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
    url: str = "",
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
    result = ExplainSet(url=url, created=timezone.now(), id=str(uuid.uuid4()))
    thread_local_query_count.queries = []
    try:
        CursorWrapper._execute = _new_execute  # type:ignore # noqa
        CursorWrapper._executemany = _new_executemany  # type:ignore
        yield result
    finally:
        CursorWrapper._execute = CursorWrapper._original_execute  # type:ignore
        CursorWrapper._executemany = CursorWrapper._original_executemany  # type:ignore
        queries_after = thread_local_query_count.queries.copy()
    logger.debug(f"Captured {len(queries_after)} queries")

    for index, q in enumerate(queries_after):
        result.queries.append(
            Explain(
                index=index,
                duration=float(q["time"]),
                sql=sqlparse.format(q["sql"], reindent=True, keyword_case="upper"),
                stack_trace="".join(traceback.format_stack()[-trace_limit:-2]),
                db_alias=db_alias,
            )
        )
