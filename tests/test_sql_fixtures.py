"""Run the SQL in the Genie skills on local Apache Spark against small made-up fixtures.

This checks query logic only. It does not prove that the queries match live Databricks
system tables or metric views. Needs Java 17 or later and `pyspark` on the Python path,
for example from a local Apache Spark install. Without them the module is skipped.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

pytest.importorskip("pyspark")
if shutil.which("java") is None:
    pytest.skip("Java is required for local Spark", allow_module_level=True)

from pyspark.sql import SparkSession  # noqa: E402

REPOSITORY = Path(__file__).resolve().parents[1]
TODAY = "DATE'2026-10-20'"


def sql_after(skill_name: str, heading: str) -> str:
    text = (REPOSITORY / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
    section = text.split(f"\n{heading}\n", 1)[1]
    return re.search(r"```sql\n(.*?)```", section, re.DOTALL).group(1)


def substitute(sql: str, replacements: dict[str, str]) -> str:
    for old, new in replacements.items():
        assert old in sql, old
        sql = sql.replace(old, new)
    return sql


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


@pytest.fixture(scope="module")
def spark():
    session = (
        SparkSession.builder.master("local[1]")
        .appName("genie-skill-sql-fixtures")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "1")
        .getOrCreate()
    )
    yield session
    session.stop()


TIMELINE_COLUMNS = (
    "workspace_id BIGINT, job_id STRING, run_id STRING, period_start_time TIMESTAMP, "
    "period_end_time TIMESTAMP, trigger_type STRING, result_state STRING"
)
TIMELINE_ROWS = [
    # prior window: one plain run
    (1, "job_a", "a1", "2026-10-08 10:00:00", "2026-10-08 10:10:00", "PERIODIC", "SUCCEEDED"),
    # current window: three hourly slices, failure, then a repair attempt under the same run_id
    (1, "job_a", "a2", "2026-10-15 09:30:00", "2026-10-15 10:00:00", "PERIODIC", None),
    (1, "job_a", "a2", "2026-10-15 10:00:00", "2026-10-15 11:00:00", "PERIODIC", None),
    (1, "job_a", "a2", "2026-10-15 11:00:00", "2026-10-15 11:20:00", "PERIODIC", "FAILED"),
    (1, "job_a", "a2", "2026-10-15 12:00:00", "2026-10-15 12:05:00", "PERIODIC", "SUCCEEDED"),
    # current window: an explicit retry run
    (1, "job_a", "a3", "2026-10-16 08:00:00", "2026-10-16 08:05:00", "ONETIME_RETRY", "SUCCEEDED"),
    (1, "job_a", "a4", "2026-10-17 07:00:00", "2026-10-17 07:15:00", "PERIODIC", "TIMED_OUT"),
    # still running: no final result state, so excluded
    (1, "job_a", "a5", "2026-10-18 22:00:00", "2026-10-18 23:00:00", "PERIODIC", None),
    # starts in the prior window, ends in the current window: assigned to current
    (1, "job_b", "b1", "2026-10-12 23:30:00", "2026-10-13 00:00:00", "PERIODIC", None),
    (1, "job_b", "b1", "2026-10-13 00:00:00", "2026-10-13 00:40:00", "PERIODIC", "SUCCEEDED"),
    # never began: start equals end
    (1, "job_b", "b2", "2026-10-09 05:00:00", "2026-10-09 05:00:00", "PERIODIC", "CANCELLED"),
    # completed on the incomplete current day: excluded
    (1, "job_b", "b3", "2026-10-20 01:00:00", "2026-10-20 01:10:00", "PERIODIC", "SUCCEEDED"),
    # before both windows: excluded
    (1, "job_b", "b4", "2026-10-01 01:00:00", "2026-10-01 01:10:00", "PERIODIC", "SUCCEEDED"),
    (1, "job_b", "b5", "2026-10-10 03:00:00", "2026-10-10 03:20:00", "PERIODIC", "FAILED"),
    # another workspace in the same account: excluded by the workspace filter
    (2, "job_z", "z1", "2026-10-15 01:00:00", "2026-10-15 01:10:00", "PERIODIC", "FAILED"),
]


def radar_sql(spark, rank_limit: str = "20") -> str:
    rows = [(*row[:3], ts(row[3]), ts(row[4]), *row[5:]) for row in TIMELINE_ROWS]
    spark.createDataFrame(rows, TIMELINE_COLUMNS).createOrReplaceTempView("job_run_timeline")
    return substitute(
        sql_after("workload-radar", "## Read-only query shape"),
        {
            "system.lakeflow.job_run_timeline": "job_run_timeline",
            "current_date()": TODAY,
            ":workspace_id": "1",
            "job_rank <= 20": f"job_rank <= {rank_limit}",
        },
    )


def test_workload_radar_job_query_on_sliced_and_repaired_runs(spark) -> None:
    sql = radar_sql(spark)

    result = {
        (row.period, row.job_id): (
            row.run_count,
            float(row.median_duration_seconds),
            row.p95_duration_seconds,
            row.non_success_count,
            row.explicit_retry_runs,
            row.repair_like_attempts_heuristic,
        )
        for row in spark.sql(sql).collect()
    }

    assert result == {
        ("prior_7d", "job_a"): (1, 600.0, 600, 0, 0, 0),
        ("current_7d", "job_a"): (3, 900.0, 6900, 1, 1, 1),
        ("prior_7d", "job_b"): (2, 600.0, 1200, 2, 0, 0),
        ("current_7d", "job_b"): (1, 4200.0, 4200, 0, 0, 0),
    }


def test_workload_radar_keeps_the_top_jobs_per_window(spark) -> None:
    rows = spark.sql(radar_sql(spark, rank_limit="1")).collect()

    assert {(row.period, row.job_id, row.job_rank) for row in rows} == {
        ("current_7d", "job_a", 1),
        ("prior_7d", "job_b", 1),
    }


def test_cost_investigator_query_keeps_corrections_and_time_ranged_prices(spark) -> None:
    usage = [
        ("1", "2026-03-02", "2026-03-02 01:00:00", "aws", "SKU_P", 12.0, "ORIGINAL"),
        ("1", "2026-03-03", "2026-03-02 01:00:00", "aws", "SKU_P", -12.0, "RETRACTION"),
        ("1", "2026-03-03", "2026-03-02 01:00:00", "aws", "SKU_P", 9.0, "RESTATEMENT"),
        ("1", "2026-03-05", "2026-03-05 02:00:00", "aws", "SKU_Q", 4.0, "ORIGINAL"),
        ("1", "2026-03-06", "2026-03-06 02:00:00", "aws", "SKU_R", 2.0, "ORIGINAL"),
        ("1", "2026-04-01", "2026-04-01 02:00:00", "aws", "SKU_Q", 100.0, "ORIGINAL"),
        # another workspace in the same account: excluded by the workspace filter
        ("2", "2026-03-05", "2026-03-05 02:00:00", "aws", "SKU_Q", 50.0, "ORIGINAL"),
    ]
    spark.createDataFrame(
        [(ws, datetime.fromisoformat(d).date(), ts(t), *rest) for ws, d, t, *rest in usage],
        "workspace_id STRING, usage_date DATE, usage_start_time TIMESTAMP, cloud STRING, "
        "sku_name STRING, usage_quantity DOUBLE, record_type STRING",
    ).createOrReplaceTempView("usage")

    def price(sku, start, end, default, effective):
        pricing = {"default": Decimal(default), "effective_list": {"default": Decimal(effective)}}
        return (sku, "aws", ts(start), ts(end) if end else None, "USD", pricing)

    prices = [
        price("SKU_P", "2026-01-01 00:00:00", None, "2.50", "2.00"),
        price("SKU_Q", "2026-01-01 00:00:00", "2026-03-01 00:00:00", "9.00", "9.00"),
        price("SKU_Q", "2026-03-01 00:00:00", None, "1.25", "1.25"),
    ]
    spark.createDataFrame(
        prices,
        "sku_name STRING, cloud STRING, price_start_time TIMESTAMP, price_end_time TIMESTAMP, "
        "currency_code STRING, pricing STRUCT<default: DECIMAL(10,2), "
        "effective_list: STRUCT<default: DECIMAL(10,2)>>",
    ).createOrReplaceTempView("list_prices")
    sql = substitute(
        sql_after("cost-investigator", "## Read-only query pattern"),
        {
            "system.billing.usage": "usage",
            "system.billing.list_prices": "list_prices",
            ":start_date": "DATE'2026-03-01'",
            ":end_date": "DATE'2026-04-01'",
            ":workspace_id": "'1'",
        },
    )

    result = {
        row.sku_name: (
            row.currency_code,
            row.net_usage_quantity,
            None if row.estimated_list_cost is None else float(row.estimated_list_cost),
            row.unmatched_usage_rows,
        )
        for row in spark.sql(sql).collect()
    }

    assert result == {
        "SKU_P": ("USD", 9.0, 18.0, 0),
        "SKU_Q": ("USD", 4.0, 5.0, 0),
        "SKU_R": (None, 2.0, None, 1),
    }


def test_business_pulse_additive_query_reconciles_to_the_total(spark) -> None:
    events = [
        ("2026-09-02 10:00:00", "North", 40.0),
        ("2026-09-03 10:00:00", "South", 25.0),
        ("2026-09-04 10:00:00", "North", 10.0),
        ("2026-09-09 10:00:00", "North", 30.0),
        ("2026-09-10 10:00:00", "South", 50.0),
        ("2026-09-11 10:00:00", "East", 5.0),
        ("2026-08-30 10:00:00", "North", 999.0),
        ("2026-09-14 10:00:00", "South", 999.0),
    ]
    spark.createDataFrame(
        [(ts(t), d, v) for t, d, v in events],
        "event_time TIMESTAMP, dimension_name STRING, metric_value DOUBLE",
    ).createOrReplaceTempView("fact_table")
    sql = substitute(
        sql_after("business-pulse", "### Raw table, additive metric"),
        {
            "catalog.schema.fact_table": "fact_table",
            ":prior_start": "TIMESTAMP'2026-09-01 00:00:00'",
            ":current_start": "TIMESTAMP'2026-09-08 00:00:00'",
            ":prior_end": "TIMESTAMP'2026-09-08 00:00:00'",
            ":current_end": "TIMESTAMP'2026-09-14 00:00:00'",
        },
    )

    rows = spark.sql(sql).collect()
    result = [(row.dimension_name, row.prior_value, row.current_value) for row in rows]

    assert result == [("South", 25.0, 50.0), ("North", 50.0, 30.0), ("East", 0.0, 5.0)]
    assert sum(row.contribution_delta for row in rows) == pytest.approx(85.0 - 75.0)


@pytest.mark.parametrize(
    ("skill_name", "expected"),
    [
        ("cost-investigator", [("SKU_A", 8.0, 16.0), ("SKU_B", 4.0, 12.0)]),
        ("business-pulse", [("North", 130.0, 100.0), ("West", 20.0, 0.0), ("South", 70.0, 80.0)]),
    ],
)
def test_built_in_samples_match_their_stated_results(spark, skill_name, expected) -> None:
    rows = spark.sql(sql_after(skill_name, "## Built-in sample (only on request)")).collect()
    assert [tuple(float(v) if i else v for i, v in enumerate(row[:3])) for row in rows] == expected


def test_workload_radar_sample_matches_its_stated_result(spark) -> None:
    rows = spark.sql(sql_after("workload-radar", "## Built-in sample (only on request)")).collect()
    result = {
        row.period: (
            row.runs,
            float(row.median_run_seconds),
            row.failures,
            row.retries,
            float(row.estimated_list_cost_usd),
            row.query_errors,
        )
        for row in rows
    }
    assert result == {
        "prior_7d": (3, 100.0, 1, 0, 20.0, 5),
        "current_7d": (4, 195.0, 1, 1, 32.0, 14),
    }
