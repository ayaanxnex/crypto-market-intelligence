import json
import os
import pandas as pd

COLUMNS = [
    "id", "symbol", "name", "image", "current_price", "high_24h", "low_24h",
    "total_volume", "market_cap", "market_cap_rank", "fully_diluted_valuation",
    "price_change_24h", "price_change_percentage_24h",
    "price_change_percentage_1h_in_currency", "price_change_percentage_7d_in_currency",
    "market_cap_change_24h", "market_cap_change_percentage_24h",
    "circulating_supply", "total_supply", "max_supply",
    "ath", "ath_change_percentage", "ath_date",
    "atl", "atl_change_percentage", "atl_date",
    "last_updated", "sparkline_in_7d",
]


def transform_markets(coins):
    df = pd.DataFrame([c.model_dump() for c in coins], columns=COLUMNS)
    if df.empty:
        return df

    df["market_cap_rank"] = df["market_cap_rank"].astype("Int64")
    # Store the sparkline dict as a JSON string so it fits in a text column.
    df["sparkline_in_7d"] = df["sparkline_in_7d"].apply(lambda s: json.dumps(s) if s else None)

    df["volatility_spread"] = df.high_24h - df.low_24h
    df["volatility_pct"] = ((df.volatility_spread / df.low_24h.where(df.low_24h > 0)) * 100).fillna(0)
    df["liquidity_ratio"] = (df.total_volume / df.market_cap.where(df.market_cap > 0)).fillna(0)
    threshold = float(os.getenv("VOLATILITY_THRESHOLD", "10"))
    df["is_volatility_alert"] = df.volatility_pct > threshold
    return df
