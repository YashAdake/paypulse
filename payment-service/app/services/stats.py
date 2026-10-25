from typing import Any

from psycopg import AsyncConnection

# All maths happens here in SQL; callers (and later the LLM) only read the results.
# now() is the database clock, so app-server clock drift can't skew the window.
_STATS_SQL = """
WITH recent AS (
    SELECT bank, method, status, error_code, latency_ms
    FROM payments
    WHERE created_at >= now() - make_interval(secs => %(window_seconds)s)
),
totals AS (
    SELECT bank,
           method,
           count(*)                                                AS total,
           avg((status = 'SUCCESS')::int)                          AS success_rate,
           percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms
    FROM recent
    GROUP BY bank, method
),
ranked_errors AS (
    -- Most frequent error per bank+method; ties broken by name so results are stable.
    SELECT bank,
           method,
           error_code,
           row_number() OVER (PARTITION BY bank, method
                              ORDER BY count(*) DESC, error_code) AS rn
    FROM recent
    WHERE error_code IS NOT NULL
    GROUP BY bank, method, error_code
)
SELECT t.bank,
       t.method,
       t.total,
       round(t.success_rate, 4)::float8 AS success_rate,
       e.error_code                     AS top_error_code,
       round(t.p95_latency_ms)::int     AS p95_latency_ms
FROM totals t
LEFT JOIN ranked_errors e
       ON e.bank = t.bank AND e.method = t.method AND e.rn = 1
ORDER BY t.bank, t.method
"""


async def get_stats(conn: AsyncConnection, window_seconds: int) -> list[dict[str, Any]]:
    """Per bank+method stats for the last window_seconds. Pairs with no traffic are omitted."""
    cur = await conn.execute(_STATS_SQL, {"window_seconds": window_seconds})
    return await cur.fetchall()


_TIMESERIES_SQL = """
SELECT bank,
       date_bin(make_interval(secs => %(bucket_seconds)s), created_at,
                TIMESTAMPTZ '2000-01-01')                    AS bucket_start,
       count(*)                                              AS total,
       round(avg((status = 'SUCCESS')::int), 4)::float8      AS success_rate
FROM payments
WHERE created_at >= now() - make_interval(secs => %(window_seconds)s)
GROUP BY bank, bucket_start
ORDER BY bucket_start, bank
"""


async def get_timeseries(
    conn: AsyncConnection, window_seconds: int, bucket_seconds: int
) -> list[dict[str, Any]]:
    """Success rate per bank in fixed time buckets, for the live chart."""
    cur = await conn.execute(
        _TIMESERIES_SQL, {"window_seconds": window_seconds, "bucket_seconds": bucket_seconds}
    )
    return await cur.fetchall()


# The investigation's evidence. "current" is the last window; "baseline" is the period
# just before it, so the LLM can compare without doing any arithmetic itself.
_BREAKDOWN_BY_METHOD_SQL = """
WITH scoped AS (
    SELECT method, status, latency_ms,
           created_at >= now() - make_interval(secs => %(window_seconds)s) AS is_current
    FROM payments
    WHERE bank = %(bank)s
      -- Casts matter: psycopg sends small ints as int2, and int2 + int2 can overflow.
      AND created_at >= now() - make_interval(
          secs => %(window_seconds)s::int + %(baseline_seconds)s::int)
)
SELECT method,
       count(*) FILTER (WHERE is_current) AS current_total,
       round(avg((status = 'SUCCESS')::int) FILTER (WHERE is_current), 4)::float8
           AS current_success_rate,
       round(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
             FILTER (WHERE is_current))::int
           AS current_p95_latency_ms,
       count(*) FILTER (WHERE NOT is_current) AS baseline_total,
       round(avg((status = 'SUCCESS')::int) FILTER (WHERE NOT is_current), 4)::float8
           AS baseline_success_rate,
       round(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
             FILTER (WHERE NOT is_current))::int
           AS baseline_p95_latency_ms
FROM scoped
GROUP BY method
ORDER BY method
"""

_BREAKDOWN_ERRORS_SQL = """
SELECT error_code,
       count(*)                                                AS count,
       round(count(*)::numeric / sum(count(*)) OVER (), 4)::float8 AS share_of_failures,
       round(avg(latency_ms))::int                             AS avg_latency_ms
FROM payments
WHERE bank = %(bank)s
  AND status = 'FAILED'
  AND created_at >= now() - make_interval(secs => %(window_seconds)s)
GROUP BY error_code
ORDER BY count DESC, error_code
"""

_BREAKDOWN_BANKS_SQL = """
SELECT bank,
       count(*)                                          AS total,
       round(avg((status = 'SUCCESS')::int), 4)::float8  AS success_rate
FROM payments
WHERE created_at >= now() - make_interval(secs => %(window_seconds)s)
GROUP BY bank
ORDER BY bank
"""


async def get_breakdown(
    conn: AsyncConnection, bank: str, window_seconds: int, baseline_seconds: int
) -> dict[str, Any]:
    params = {"bank": bank, "window_seconds": window_seconds, "baseline_seconds": baseline_seconds}
    by_method = await (await conn.execute(_BREAKDOWN_BY_METHOD_SQL, params)).fetchall()
    errors = await (await conn.execute(_BREAKDOWN_ERRORS_SQL, params)).fetchall()
    banks = await (await conn.execute(_BREAKDOWN_BANKS_SQL, params)).fetchall()
    return {"by_method": by_method, "errors": errors, "all_banks": banks}
