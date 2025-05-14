import datetime
import functools
import logging
import time
import traceback
import uuid
import webbrowser
from contextlib import contextmanager
from dataclasses import dataclass, field
from itertools import groupby
from threading import local
from typing import Any

import sqlglot
import sqlglot.expressions as exp
from django.db import connection, connections
from django.db.backends.utils import CursorWrapper
from django.utils import timezone

from django_pev.dalibo import PevResponse, upload_sql_plan
from django_pev.exceptions import PevException

from . import indexes

logger = logging.Logger("django_pev")


thread_local_query_count = local()

CursorWrapper._original_execute = CursorWrapper._execute  # type:ignore
CursorWrapper._original_executemany = CursorWrapper._executemany  # type:ignore


class record_sql:
    """Record the SQL query and parameters for use in the explain view"""

    def __init__(self, cursor_wrapper: CursorWrapper, sql: str, params: Any):
        """Record the SQL query and parameters for use in the explain view"""
        self.cursor_wrapper = cursor_wrapper
        self.sql = sql
        self.params = params
        self.start_time = time.time()
        self.stack_trace = ""

    def __enter__(self):
        thread_local_query_count.query_count = getattr(thread_local_query_count, "query_count", 0) + 1
        frame_stack = traceback.extract_stack(limit=100)
        filtered_frame_stack = [
            x for x in frame_stack if not ("django_pev" in x.filename or "django/db" in x.filename)
        ][-10:]
        self.stack_trace = "".join(traceback.format_list(filtered_frame_stack))

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        thread_local_query_count.queries = getattr(thread_local_query_count, "queries", []) + [
            {
                "time": duration,
                "sql": self.cursor_wrapper.cursor.mogrify(self.sql, self.params).decode("utf-8"),
                "stack_trace": self.stack_trace,
            }
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
    fingerprint: str

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

    @functools.cache  # noqa
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

    @functools.cache  # noqa
    def optimization_prompt(self, analyze: bool = True) -> str:
        # Extract tables from query
        tables: set[tuple[str, str]] = set()
        query = self.sql
        try:
            parsed = sqlglot.parse_one(query)
            for s_table in parsed.find_all(exp.Table):
                tables.add((s_table.args.get("schema", "public"), s_table.name))
        except Exception as e:
            return f"Error: {str(e)}"

        # Fetch schema and indexes for each table
        table_schemas = {}
        table_indexes = {}

        for table_schema, table_name in tables:
            # Schema: columns and types
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
                    [table_schema, table_name],  # type: ignore
                )
                table_schemas[table_name] = cursor.fetchall()
            # Indexes: reuse get_indexes
            table_indexes[table_name] = [i for i in indexes.get_indexes() if i.table == table_name]

        # Prepare prompt for AI
        plan_json = self.explain(analyze=analyze)
        ai_prompt = f"""You are an expert PostgreSQL query optimizer. Analyze this query and suggest optimizations.

Original Query:
{query}

Current Execution Plan:
{plan_json}

Table Schemas:
{
            chr(10).join(
                f"{table}:{chr(10)}"
                + chr(10).join(
                    f"- {col}: {dtype} {'(nullable)' if nullable == 'YES' else ''}" for col, dtype, nullable in schema
                )
                for table, schema in table_schemas.items()
            )
        }

Current Indexes:
{
            chr(10).join(
                f"{table}:{chr(10)}" + chr(10).join(f"- {idx.name} ({idx.columns_formatted})" for idx in indexes)
                for table, indexes in table_indexes.items()
            )
        }

Please analyze the query, execution plan, table schemas and existing indexes. Provide optimization suggestions in the following markdown format:

## Optimized SQL Query
```sql
<optimized_sql>
```

## Suggested Indexes
```sql
<suggested_indexes>
```
## Explanation
<explanation>


Extra instructions. Please focus on:
1. Query structure and join optimizations
2. Index recommendations considering existing indexes
3. Specific bottlenecks shown in the execution plan
4. Schema-aware optimizations

Ensure the optimized query maintains the exact same logic and results as the original.
"""
        return ai_prompt


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

    @property
    def nplusones(self) -> dict[Explain, int]:
        ret = {}
        for _, group in groupby(sorted(self.queries, key=lambda q: q.fingerprint), key=lambda q: q.fingerprint):
            group_list = list(group)
            if len(group_list) > 3:
                ret[group_list[0]] = len(group_list)
        return ret


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
                sql=sqlglot.transpile(q["sql"], read="postgres", pretty=True)[0],
                stack_trace=q["stack_trace"],
                db_alias=db_alias,
                fingerprint=generate_fingerprint(q["sql"]) or q["sql"],
            )
        )


def generate_fingerprint(sql_query: str) -> str | None:
    try:
        # Parse the query
        expression_tree = sqlglot.parse_one(sql_query, read="postgres")

        # Define a transformer function to replace literals
        def replace_literals(node):
            # Check if the node is a Literal (number, string, boolean, etc.)
            if isinstance(node, exp.Literal):
                # Replace the literal with a placeholder.
                # You could use '?' or a string like '<value>'
                return exp.Placeholder()  # or exp.Literal.from_arg('<value>')
            return node  # Return the node unchanged if it's not a literal

        # Apply the transformation across the entire AST
        fingerprinted_tree = expression_tree.transform(replace_literals)

        # Generate the SQL string back from the modified AST
        # Use pretty=False and identify=False for canonical representation
        fingerprint_sql = fingerprinted_tree.sql(pretty=False, identify=False)

        return fingerprint_sql

    except sqlglot.errors.ParseError as e:
        print(f"Error parsing query: {e}")
        return None  # Handle parsing errors
