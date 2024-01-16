with index_columns as (
  select
    n.nspname as schema,
    t.relname as table,
    i.relname as name,
    array_agg(a.attname order by  array_position(ix.indkey, a.attnum) )  as column_names
  from
    pg_catalog.pg_class t
    join pg_catalog.pg_attribute a on t.oid = a.attrelid
    join pg_catalog.pg_index ix on t.oid = ix.indrelid
    join pg_catalog.pg_class i on a.attnum = any(ix.indkey)
    and i.oid = ix.indexrelid
    join pg_catalog.pg_namespace n on n.oid = t.relnamespace
  where
    t.relkind = 'r'
  group by
    1,2,3
  order by
    1,2
),
index_stats as (
    SELECT
        ui.schemaname AS schema,
        t.relname AS table,
        ix.relname AS name,
        regexp_replace(pg_get_indexdef(i.indexrelid), '.* USING ([^ ]*) \(.*', '\1') AS using,
        indisunique AS unique,
        indisprimary AS primary,
        indisvalid AS valid,
        indexprs::text,
        indpred::text,
        pg_get_indexdef(i.indexrelid) AS definition,
        CASE WHEN pg_statio_user_indexes.idx_blks_hit + pg_statio_user_indexes.idx_blks_read = 0 THEN
            0
        ELSE
            ROUND(1.0 * pg_statio_user_indexes.idx_blks_hit / (pg_statio_user_indexes.idx_blks_hit + pg_statio_user_indexes.idx_blks_read), 2)
        END AS hit_rate,
        idx_scan as index_scans,
        pg_table_size(ix.oid) AS size_bytes
    FROM
        pg_index i
    INNER JOIN
        pg_class t ON t.oid = i.indrelid
    INNER JOIN
        pg_class ix ON ix.oid = i.indexrelid
    LEFT JOIN
        pg_stat_user_indexes ui ON ui.indexrelid = i.indexrelid
    LEFT JOIN
        pg_statio_user_indexes ON pg_statio_user_indexes.indexrelid = i.indexrelid
    WHERE
        ui.schemaname IS NOT NULL
)
select
  index_columns.schema,
  index_columns.table,
  index_columns.name,
  column_names,
  index_stats.using,
  index_stats.unique,
  index_stats.primary,
  index_stats.valid,
  index_stats.indexprs,
  index_stats.indpred,
  index_stats.definition,
  index_stats.hit_rate,
  index_stats.index_scans,
  index_stats.size_bytes,
  null as covered_by
from
  index_columns
join
    index_stats on
   (     index_columns.schema = index_stats.schema
    and
        index_columns.table = index_stats.table
    and
        index_columns.name = index_stats.name
   )
   ;