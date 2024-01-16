import dataclasses
from datetime import datetime

from django.db import connection


def get_tables_missing_indexes() -> list[tuple[str, str, str, int]]:
    with connection.cursor() as cursor:
        sql = """
    SELECT
        schemaname AS schema,
        relname AS table,
    FROM
        pg_stat_user_tables
    WHERE
        idx_scan > 0
        AND (100 * idx_scan / (seq_scan + idx_scan)) < 95
        AND n_live_tup >= 10000
    ORDER BY
        n_live_tup DESC,
        relname ASC
        """
        cursor.execute(sql)
        return cursor.fetchall()


@dataclasses.dataclass
class TableInfo:
    schema: str
    name: str
    last_vacuum: datetime | None
    last_autovacuum: datetime | None
    last_analyze: datetime | None
    last_autoanalyze: datetime | None
    dead_rows: int
    live_rows: int
    idx_scan: int
    seq_scan: int

    @property
    def requires_index(self) -> bool:
        return (
            self.idx_scan > 0
            and (100 * self.idx_scan / (self.seq_scan + self.idx_scan)) < 95
            and self.live_rows >= 10000
        )

    @property
    def index_hit_rate(self) -> float:
        return self.idx_scan / (self.seq_scan + self.idx_scan) if self.idx_scan > 0 else 0

    @property
    def index_hit_rate_formatted(self) -> str:
        return f"{self.index_hit_rate * 100: 0.2f}%" if self.index_hit_rate else ""


def get_maintenance_info() -> list[TableInfo]:
    sql = """
            SELECT
                schemaname AS schema,
                relname AS name,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze,
                n_dead_tup AS dead_rows,
                n_live_tup AS live_rows,
                idx_scan,
                seq_scan
            FROM
                pg_stat_user_tables
            ORDER BY
                1, 2
    """
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return [TableInfo(*row) for row in cursor.fetchall()]
