import dataclasses
from typing import Literal

from django.db import connection


@dataclasses.dataclass
class RelationSpaceStat:
    schema: str
    name: str
    type: Literal["table", "index"]
    size_bytes: int
    row_estimate: int


def get_database_size() -> int:
    """Returns the size of the current database in bytes"""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT pg_database_size(current_database()) as database_size
        """
        )
        return cursor.fetchone()[0]


def get_relation_sizes() -> list[RelationSpaceStat]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
SELECT
    n.nspname AS schema,
    c.relname AS name,
    CASE WHEN c.relkind = 'r' THEN 'table' ELSE 'index' END AS type,
    pg_table_size(c.oid) AS size_bytes,
    (case WHEN reltuples < 0 THEN 0 else reltuples END)::int as row_estimate
FROM
    pg_class c
LEFT JOIN
    pg_namespace n ON n.oid = c.relnamespace
WHERE
    n.nspname NOT IN ('pg_catalog', 'information_schema')
    AND n.nspname !~ '^pg_toast'
    AND c.relkind IN ('r', 'i')
ORDER BY
    pg_table_size(c.oid) DESC,
    2 ASC
"""
        )
        return [RelationSpaceStat(*row) for row in cursor.fetchall()]


def get_table_sizes() -> list[RelationSpaceStat]:
    return [r for r in get_relation_sizes() if r.type == "table"]


def get_index_sizes() -> list[RelationSpaceStat]:
    return [r for r in get_relation_sizes() if r.type == "index"]
