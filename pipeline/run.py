import logging
from .extract import extract_markets
from .validate import validate_markets
from .transform import transform_markets
from .load import get_engine,save_snapshot
logging.basicConfig(level=logging.INFO)
def run_pipeline():
    raw=extract_markets(50); valid,rejected=validate_markets(raw); df=transform_markets(valid)
    save_snapshot(df,get_engine())
    alerts=df[df.is_volatility_alert].to_dict("records") if not df.empty else []
    return {"fetched":len(raw),"valid":len(valid),"rejected":len(rejected),"saved":len(df),"alerts":alerts}
if __name__=="__main__":
    r=run_pipeline()
    print(f"Complete: {r['valid']}/{r['fetched']} valid; {r['saved']} saved; {len(r['alerts'])} alerts.")
