import dataclasses
from decimal import Decimal
from itertools import groupby
from pathlib import Path

from django.db import connection


@dataclasses.dataclass
class IndexInfo:
    schema: str
    table: str
    name: str
    columns: list[str]
    using: str
    unique: bool
    primary: bool
    valid: bool
    indexprs: str | None
    indpred: str | None
    definition: str
    hit_rate: Decimal
    index_scans: int
    size_bytes: int
    covered_by: "IndexInfo | None"

    @property
    def is_unused(self) -> bool:
        return self.index_scans < 50

    @property
    def is_duplicated(self) -> bool:
        return bool(self.covered_by)

    @property
    def columns_formatted(self) -> str:
        return ", ".join(self.columns)

    @property
    def table_key(self) -> str:
        return f"{self.schema}.{self.table}"

    def index_covers(self, columns: list[str]) -> bool:
        """Returns true if this index covers the given columns"""
        return self.columns[: len(columns)] == columns


def get_indexes() -> list[IndexInfo]:
    with connection.cursor() as cursor:
        sql = (Path(__file__).parent / "index_lookup.sql").read_text()
        cursor.execute(sql)
        indexes = list(IndexInfo(*c) for c in cursor.fetchall())
    _update_indexes_with_duplicated_indexes(indexes)
    return indexes


def get_total_index_hitrate() -> float:
    """Total hit rate with all indexes"""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                (sum(idx_blks_hit)) / nullif(sum(idx_blks_hit + idx_blks_read), 0) AS rate
            FROM
                pg_statio_user_indexes
        """
        )
        return cursor.fetchone()[0]


def _update_indexes_with_duplicated_indexes(
    indexes: list[IndexInfo] | None = None,
) -> None:
    """Modifies a list of indexes a reference to the other index that covers it"""
    indexes = indexes or get_indexes()
    indexes_by_table = {key: list(group) for key, group in groupby(indexes, lambda i: i.table_key)}
    for index in indexes:
        if index.valid and not index.primary and not index.unique:
            for other_index in indexes_by_table[index.table_key]:
                if (
                    other_index.valid
                    and other_index.name != index.name
                    and other_index.index_covers(index.columns)
                    and other_index.using == index.using
                    and other_index.indexprs == index.indexprs
                    and other_index.indpred == index.indpred
                ):
                    index.covered_by = other_index


def get_index_stats(indexes: list[IndexInfo] | None = None) -> dict:
    indexes = indexes or get_indexes()

    ret = {
        "total_index_hitrate": get_total_index_hitrate() * 100,
        "total_indexes_size": sum(i.size_bytes for i in indexes),
        "total_duplicated_indexes_size": sum(i.size_bytes for i in indexes if i.is_duplicated),
        "total_unused_indexes_size": sum(i.size_bytes for i in indexes if i.is_unused),
        "count_indexes": len(indexes),
        "count_duplicated_indexes": sum(1 for i in indexes if i.is_duplicated),
        "count_unused_indexes": sum(1 for i in indexes if i.is_unused),
    }

    ret["percent_duplicated_indexes"] = float(ret["total_duplicated_indexes_size"]) / ret["total_indexes_size"] * 100  # type:ignore
    ret["percent_unused_indexes"] = float(ret["total_unused_indexes_size"]) / ret["total_indexes_size"] * 100  # type:ignore

    return ret
