import os
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

# New table name: the old "market_snapshots" table was created by an earlier
# version of the pipeline and has a different set of columns/types.
SNAPSHOT_TABLE = "market_snapshots_v2"
RUNS_TABLE = "pipeline_runs"


def get_engine():
    url = os.getenv("DATABASE_URL", "sqlite:///crypto_market.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    if url.startswith("sqlite"):
        return create_engine(url, pool_pre_ping=True, connect_args={"check_same_thread": False})

    # PostgreSQL (Neon / pgbouncer pooler): disable server-side prepared statements.
    # Without this, reused connections raise DuplicatePreparedStatement.
    # NullPool: serverless functions should not keep connections between calls.
    return create_engine(url, poolclass=NullPool, connect_args={"prepare_threshold": None})


def save_snapshot(df, engine=None):
    if df.empty:
        return 0
    engine = engine or get_engine()
    out = df.copy()
    out.insert(0, "timestamp", datetime.now(timezone.utc).isoformat())
    out.rename(columns={"id": "coin_id"}).to_sql(SNAPSHOT_TABLE, engine, if_exists="append", index=False)
    return len(out)


def read_latest(engine=None):
    engine = engine or get_engine()
    try:
        with engine.connect() as c:
            ts = c.execute(text(f"SELECT MAX(timestamp) FROM {SNAPSHOT_TABLE}")).scalar()
            if not ts:
                return pd.DataFrame()
            return pd.read_sql(text(f"SELECT * FROM {SNAPSHOT_TABLE} WHERE timestamp=:ts"), c, params={"ts": ts})
    except Exception:
        return pd.DataFrame()


def record_run(stats, engine=None):
    """Append one row to the pipeline_runs audit table."""
    engine = engine or get_engine()
    row = {"run_at": datetime.now(timezone.utc).isoformat(), **stats}
    pd.DataFrame([row]).to_sql(RUNS_TABLE, engine, if_exists="append", index=False)


def read_runs(limit=30, engine=None):
    engine = engine or get_engine()
    try:
        with engine.connect() as c:
            df = pd.read_sql(text(f"SELECT * FROM {RUNS_TABLE} ORDER BY run_at DESC LIMIT :n"), c, params={"n": int(limit)})
        df = df.astype(object).where(pd.notna(df), None)
        return list(reversed(df.to_dict("records")))   # oldest -> newest
    except Exception:
        return []


def database_health(engine=None):
    try:
        with (engine or get_engine()).connect() as c:
            n = c.execute(text(f"SELECT COUNT(*) FROM {SNAPSHOT_TABLE}")).scalar_one()
        return {"database": "connected", "stored_records": int(n)}
    except Exception as e:
        return {"database": "not initialized", "stored_records": 0, "detail": str(e)[:150]}
