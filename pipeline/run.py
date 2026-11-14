
import logging
import time

from .extract import extract_markets
from .validate import validate_markets
from .transform import transform_markets
from .load import get_engine, save_snapshot, record_run

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_pipeline():
    started = time.time()
    engine = get_engine()

    raw = []
    valid = []
    rejected = []
    alerts = []
    df = None
    saved = 0

    try:
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
            "source": "local",
            "error": None
        }

        try:
            record_run(stats, engine)
        except Exception:
            logger.exception("Could not save successful run history")

        return {
            "fetched": len(raw),
            "valid": len(valid),
            "rejected": len(rejected),
            "saved": int(saved),
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
            "source": "local",
            "error": str(e)[:500]
        }

        try:
            record_run(failed_stats, engine)
        except Exception:
            logger.exception("Could not save failed run history")

        raise


if __name__ == "__main__":
    result = run_pipeline()
    print(
        f"Complete: {result['valid']}/{result['fetched']} valid; "
        f"{result['saved']} saved; "
        f"{len(result['alerts'])} alerts."
    )
