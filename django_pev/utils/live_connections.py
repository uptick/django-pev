import dataclasses
from datetime import datetime

from django.db import connection


@dataclasses.dataclass
class ConnectionInfo:
    pid: int
    database: str
    user: str
    source: str
    ip: str
    backend_start: datetime
    query_start: datetime | None
    wait_event: str
    state: str
    query: str
    ssl: bool


def get_connections_current_database() -> list[ConnectionInfo]:
    """Returns list of postgres connections"""
    sql = """
SELECT
    pg_stat_activity.pid,
    datname AS database,
    usename AS user,
    application_name AS source,
    client_addr AS ip,
    backend_start,
    query_start,
    wait_event,
    state,
    query,
    ssl
FROM
    pg_stat_activity
LEFT JOIN
    pg_stat_ssl ON pg_stat_activity.pid = pg_stat_ssl.pid
WHERE
    datname = %s
ORDER BY
    pg_stat_activity.pid
    """
    with connection.cursor() as cursor:
        database_name = connection.get_connection_params()["database"]
        cursor.execute(sql, [database_name])
        return list(ConnectionInfo(*c) for c in cursor.fetchall())
