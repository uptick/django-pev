import dataclasses
from datetime import datetime

from django.db import OperationalError, connection

TIME_DURATION_UNITS = (
    ("week", 60 * 60 * 24 * 7 * 1000),
    ("day", 60 * 60 * 24 * 1000),
    ("hour", 60 * 60 * 1000),
    ("min", 60 * 1000),
    ("sec", 1000),
    ("ms", 1),
)


def human_time_duration(milliseconds: float) -> str:
    if milliseconds == 0:
        return "inf"
    parts = []
    for unit, div in TIME_DURATION_UNITS:
        amount, milliseconds = divmod(int(milliseconds), div)
        if amount > 0:
            parts.append("{} {}".format(amount, unit))
    return " ".join(parts[:2])


@dataclasses.dataclass
class LiveQueryInfo:
    pid: int
    database: str
    state: str
    source: str
    duration: int
    waiting: bool
    query: str
    started_at: datetime
    duration_ms: float
    user: str
    backend_type: str

    @property
    def is_long_running(self) -> bool:
        if self.duration_ms:
            return self.duration_ms > 1000
        return False


def get_live_queries_current_database() -> list[LiveQueryInfo]:
    """Returns list of live queries"""
    sql = """
SELECT
    pid,
    datname as database,
    state,
    application_name AS source,
    age(NOW(), COALESCE(query_start, xact_start)) AS duration,
    wait_event is not null as waiting,
    query,
    COALESCE(query_start, xact_start) AS started_at,
    EXTRACT(EPOCH FROM NOW() - COALESCE(query_start, xact_start)) * 1000.0 AS duration_ms,
    usename AS user,
    backend_type
FROM
    pg_stat_activity
WHERE
    pid <> pg_backend_pid()
and
    datname = current_database()
ORDER BY
COALESCE(query_start, xact_start) DESC
"""

    with connection.cursor() as cursor:
        cursor.execute(sql)
        return list(LiveQueryInfo(*c) for c in cursor.fetchall())


@dataclasses.dataclass
class QueryStatInfo:
    query: str
    query_id: str
    query_md5: str
    user: str
    total_time: float
    mean_time: float
    stddev_time: float
    shared_blks_hit: int
    shared_blks_dirtied: int
    blk_read_time: int
    temp_blks_written: int
    temp_blks_read: int
    rows: int
    calls: int
    total_percent_time: float
    total_percent_calls: float
    total_percent_shared_blks: float
    calls_per_second: float
    shared_blks_per_second: float
    rows_per_second: float
    rows_per_call: float
    shared_blks_per_call: float

    @property
    def total_time_formatted(self) -> str:
        return human_time_duration(self.total_time)

    @property
    def mean_time_formatted(self) -> str:
        return human_time_duration(self.mean_time)

    @property
    def stddev_time_formatted(self) -> str:
        return human_time_duration(self.stddev_time)


def is_pg_stat_statements_installed() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'")
            assert cursor.fetchone()
            cursor.execute("SELECT 1 FROM pg_stat_statements limit 1")
            assert cursor.fetchone()
        return True
    except (AssertionError, OperationalError):
        return False


def enable_pg_stat_statements():
    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")


def reset_pg_stat_statements():
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_stat_statements_reset()")


def get_query_stats() -> list[QueryStatInfo]:
    if not is_pg_stat_statements_installed():
        return []

    sql = """
WITH query_stats AS (
    SELECT
        LEFT(query, 10000) AS query,
        queryid as query_id,
        md5(query) as query_md5,
        rolname AS user,
        (total_exec_time) as total_time,
        mean_exec_time as mean_time,
        stddev_exec_time as stddev_time,
        shared_blks_hit,
        shared_blks_dirtied,
        blk_read_time,
        temp_blks_written,
        temp_blks_read,
        rows,
        calls
    FROM
        pg_stat_statements
    INNER JOIN
        pg_database ON pg_database.oid = pg_stat_statements.dbid
    INNER JOIN
        pg_roles ON pg_roles.oid = pg_stat_statements.userid
    WHERE
        calls > 0
    AND
        pg_database.datname = current_database()
), totals AS (
    SELECT
        SUM(total_exec_time) as total_time,
        SUM(calls) as total_calls,
        SUM(shared_blks_hit) as total_shared_blks_hit,
        SUM(shared_blks_dirtied) as total_shared_blks_dirtied,
        (extract(epoch from now()) - (select extract( epoch from stats_reset) from pg_stat_statements_info)) as total_seconds
    FROM pg_stat_statements
)
SELECT
    query,
    query_id,
    query_md5,
    query_stats.user,
    query_stats.total_time,
    mean_time,
    stddev_time,
    shared_blks_hit,
    shared_blks_dirtied,
    blk_read_time,
    temp_blks_written,
    temp_blks_read,
    rows,
    calls,
    query_stats.total_time * 100.0  / totals.total_time AS total_percent_time,
    calls * 100.0 / total_calls as total_percent_calls,
    (shared_blks_hit + shared_blks_dirtied) * 100.0 / (totals.total_shared_blks_hit + totals.total_shared_blks_dirtied) as total_percent_shared_blks,
    calls::float / total_seconds as calls_per_second,
    (shared_blks_hit + shared_blks_dirtied)::float / total_seconds as shared_blks_per_second,
    rows::float / total_seconds as rows_per_second,
    (shared_blks_hit + shared_blks_dirtied)::float / calls as shared_blks_per_call,
    rows::float/ calls as rows_per_call
FROM
    query_stats
CROSS JOIN totals
ORDER BY query_stats.TOTAL_TIME desc
LIMIT 100
"""
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return list(QueryStatInfo(*c) for c in cursor.fetchall())
