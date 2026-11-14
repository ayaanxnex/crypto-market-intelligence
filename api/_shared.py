
import json
import logging
import time

import pandas as pd

from pipeline.extract import extract_markets
from pipeline.validate import validate_markets
from pipeline.transform import transform_markets
from pipeline.load import (
    get_engine,
    save_snapshot,
    read_latest,
    record_run
)

logger = logging.getLogger(__name__)


def refresh():
    started = time.time()
    engine = None

    raw = []
    valid = []
    rejected = []
    alerts = []
    df = None
    saved = 0

    try:
        engine = get_engine()

        raw = extract_markets(50)
        valid, rejected = validate_markets(raw)
        df = transform_markets(valid)

        saved = save_snapshot(df, engine)

        if not df.empty:
            alerts = df[
                df.is_volatility_alert
            ][["id", "symbol", "name", "volatility_pct"]].to_dict("records")

        stats = {
            "fetched": len(raw),
            "valid": len(valid),
            "rejected": len(rejected),
            "saved": int(saved),
            "alerts": len(alerts),
            "duration_ms": int((time.time() - started) * 1000),
            "total_market_cap": float(df.market_cap.sum()) if not df.empty else 0.0,
            "total_volume": float(df.total_volume.sum()) if not df.empty else 0.0,
            "status": "success",
            "source": "vercel",
            "error": None
        }

        try:
            record_run(stats, engine)
        except Exception:
            logger.exception("Could not save successful Vercel run history")

        return {
            "fetched": len(raw),
            "valid": len(valid),
            "rejected": len(rejected),
            "saved": int(saved),
            "rejections": rejected[:50],
            "alerts": alerts
        }

    except Exception as e:
        failed_stats = {
            "fetched": len(raw),
            "valid": len(valid),
            "rejected": len(rejected),
            "saved": int(saved),
            "alerts": len(alerts),
            "duration_ms": int((time.time() - started) * 1000),
            "total_market_cap": float(df.market_cap.sum()) if df is not None and not df.empty else 0.0,
            "total_volume": float(df.total_volume.sum()) if df is not None and not df.empty else 0.0,
            "status": "failed",
            "source": "vercel",
            "error": str(e)[:500]
        }

        try:
            record_run(failed_stats, engine)
        except Exception:
            logger.exception("Could not save failed Vercel run history")

        raise


def serialize_latest():
    df = read_latest(get_engine())

    if df.empty:
        return {
            "coins": [],
            "message": "No snapshot available"
        }

    df = df.astype(object).where(pd.notna(df), None)
    coins = df.to_dict("records")

    for coin in coins:
        sparkline = coin.get("sparkline_in_7d")

        if isinstance(sparkline, str):
            try:
                coin["sparkline_in_7d"] = json.loads(sparkline)
            except ValueError:
                coin["sparkline_in_7d"] = None

    return {
        "coins": coins,
        "count": len(coins),
        "timestamp": coins[0].get("timestamp")
    }
