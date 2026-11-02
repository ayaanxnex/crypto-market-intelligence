import pandas as pd
def transform_markets(coins):
    cols=["id","symbol","name","current_price","high_24h","low_24h","total_volume","market_cap","price_change_percentage_24h","market_cap_rank"]
    df=pd.DataFrame([c.model_dump() for c in coins],columns=cols)
    if df.empty: return df
    df["volatility_spread"]=df.high_24h-df.low_24h
    df["volatility_pct"]=((df.volatility_spread/df.low_24h.where(df.low_24h>0))*100).fillna(0)
    df["liquidity_ratio"]=(df.total_volume/df.market_cap.where(df.market_cap>0)).fillna(0)
    df["is_volatility_alert"]=df.volatility_pct>float(__import__("os").getenv("VOLATILITY_THRESHOLD","10"))
    return df
