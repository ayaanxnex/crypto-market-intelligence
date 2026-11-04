import json
import time

import pandas as pd

from pipeline.extract import extract_markets
from pipeline.validate import validate_markets
from pipeline.transform import transform_markets
from pipeline.load import get_engine, save_snapshot, read_latest, record_run, database_health


def refresh():
    started = time.time()
    engine = get_engine()

    raw = extract_markets(50)
    valid, rejected = validate_markets(raw)
    df = transform_markets(valid)
    saved = save_snapshot(df, engine)

    if df.empty:
        alerts = []
    else:
        alerts = df[df.is_volatility_alert][["id", "symbol", "name", "volatility_pct"]].to_dict("records")

    try:
        record_run({
            "fetched": len(raw),
            "valid": len(valid),
            "rejected": len(rejected),
            "saved": int(saved),
            "alerts": len(alerts),
            "duration_ms": int((time.time() - started) * 1000),
            "total_market_cap": float(df.market_cap.sum()) if not df.empty else 0.0,
            "total_volume": float(df.total_volume.sum()) if not df.empty else 0.0,
        }, engine)
    except Exception:
        pass  # the audit log must never break a refresh

    return {
        "fetched": len(raw),
        "valid": len(valid),
        "rejected": len(rejected),
        "saved": int(saved),
        "rejections": rejected[:50],
        "alerts": alerts,
    }


def serialize_latest():
    df = read_latest(get_engine())
    if df.empty:
        return {"coins": [], "message": "No snapshot available"}
    df = df.astype(object).where(pd.notna(df), None)
    coins = df.to_dict("records")
    for c in coins:
        s = c.get("sparkline_in_7d")
        if isinstance(s, str):
            try:
                c["sparkline_in_7d"] = json.loads(s)
            except ValueError:
                c["sparkline_in_7d"] = None
    return {"coins": coins, "count": len(coins), "timestamp": coins[0].get("timestamp")}
