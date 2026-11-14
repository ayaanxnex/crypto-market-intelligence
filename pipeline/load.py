
import os
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.pool import NullPool

SNAPSHOT_TABLE = "market_snapshots_v2"
RUNS_TABLE = "pipeline_runs"


def get_engine():
    url = os.getenv("DATABASE_URL", "sqlite:///crypto_market.db")

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    if url.startswith("sqlite"):
        return create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False}
        )

    return create_engine(
        url,
        poolclass=NullPool,
        connect_args={"prepare_threshold": None}
    )


def save_snapshot(df, engine=None):
    if df.empty:
        return 0

    engine = engine or get_engine()
    out = df.copy()
    out.insert(0, "timestamp", datetime.now(timezone.utc).isoformat())

    out.rename(columns={"id": "coin_id"}).to_sql(
        SNAPSHOT_TABLE,
        engine,
        if_exists="append",
        index=False
    )

    return len(out)


def read_latest(engine=None):
    engine = engine or get_engine()

    try:
        with engine.connect() as connection:
            ts = connection.execute(
                text(f"SELECT MAX(timestamp) FROM {SNAPSHOT_TABLE}")
            ).scalar()

            if not ts:
                return pd.DataFrame()

            return pd.read_sql(
                text(f"SELECT * FROM {SNAPSHOT_TABLE} WHERE timestamp=:ts"),
                connection,
                params={"ts": ts}
            )
    except Exception:
        return pd.DataFrame()


def record_run(stats, engine=None):
    """Save one pipeline execution to the audit table."""
    engine = engine or get_engine()

    row = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "fetched": 0,
        "valid": 0,
        "rejected": 0,
        "saved": 0,
        "alerts": 0,
        "duration_ms": 0,
        "total_market_cap": 0.0,
        "total_volume": 0.0,
        "status": "success",
        "source": "unknown",
        "error": None,
        **stats
    }

    if not inspect(engine).has_table(RUNS_TABLE):
        pd.DataFrame([row]).to_sql(
            RUNS_TABLE, engine, if_exists="fail", index=False
        )
        return

    existing = {
        column["name"]
        for column in inspect(engine).get_columns(RUNS_TABLE)
    }

    column_types = {
        "run_at": "VARCHAR(40)",
        "fetched": "INTEGER",
        "valid": "INTEGER",
        "rejected": "INTEGER",
        "saved": "INTEGER",
        "alerts": "INTEGER",
        "duration_ms": "INTEGER",
        "total_market_cap": "FLOAT",
        "total_volume": "FLOAT",
        "status": "VARCHAR(20)",
        "source": "VARCHAR(30)",
        "error": "TEXT"
    }

    with engine.begin() as connection:
        for column, sql_type in column_types.items():
            if column not in existing:
                connection.execute(
                    text(
                        f"ALTER TABLE {RUNS_TABLE} "
                        f"ADD COLUMN {column} {sql_type}"
                    )
                )

    pd.DataFrame([row]).to_sql(
        RUNS_TABLE, engine, if_exists="append", index=False
    )


def read_runs(limit=30, engine=None):
    engine = engine or get_engine()

    try:
        with engine.connect() as connection:
            df = pd.read_sql(
                text(
                    f"SELECT * FROM {RUNS_TABLE} "
                    "ORDER BY run_at DESC LIMIT :n"
                ),
                connection,
                params={"n": int(limit)}
            )

        df = df.astype(object).where(pd.notna(df), None)
        return list(reversed(df.to_dict("records")))

    except Exception:
        return []


def database_health(engine=None):
    try:
        with (engine or get_engine()).connect() as connection:
            n = connection.execute(
                text(f"SELECT COUNT(*) FROM {SNAPSHOT_TABLE}")
            ).scalar_one()

        return {
            "database": "connected",
            "stored_records": int(n)
        }

    except Exception as e:
        return {
            "database": "not initialized",
            "stored_records": 0,
            "detail": str(e)[:150]
        }
