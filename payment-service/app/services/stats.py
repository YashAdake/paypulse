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
