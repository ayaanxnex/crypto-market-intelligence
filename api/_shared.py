import pandas as pd
from pipeline.extract import extract_markets
from pipeline.validate import validate_markets
from pipeline.transform import transform_markets
from pipeline.load import get_engine,save_snapshot,read_latest,database_health
def refresh():
    raw=extract_markets(50);valid,rejected=validate_markets(raw);df=transform_markets(valid);save_snapshot(df,get_engine())
    alerts=df[df.is_volatility_alert].to_dict("records") if not df.empty else []
    return {"fetched":len(raw),"valid":len(valid),"rejected":len(rejected),"alerts":alerts}
def serialize_latest():
    df=read_latest(get_engine())
    if df.empty:return {"coins":[],"message":"No snapshot available"}
    df=df.astype(object).where(pd.notna(df),None);coins=df.to_dict("records")
    return {"coins":coins,"count":len(coins),"timestamp":coins[0].get("timestamp")}
