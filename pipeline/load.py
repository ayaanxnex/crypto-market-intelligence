import os
from datetime import datetime,timezone
import pandas as pd
from sqlalchemy import create_engine,text
def get_engine():
    url=os.getenv("DATABASE_URL","sqlite:///crypto_market.db")
    if url.startswith("postgres://"): url=url.replace("postgres://","postgresql+psycopg://",1)
    elif url.startswith("postgresql://"): url=url.replace("postgresql://","postgresql+psycopg://",1)
    opts={"pool_pre_ping":True}
    if url.startswith("sqlite"): opts["connect_args"]={"check_same_thread":False}
    return create_engine(url,**opts)
def save_snapshot(df,engine=None):
    if df.empty:return 0
    engine=engine or get_engine(); out=df.copy()
    out.insert(0,"timestamp",datetime.now(timezone.utc).isoformat())
    out.rename(columns={"id":"coin_id"}).to_sql("market_snapshots",engine,if_exists="append",index=False)
    return len(out)
def read_latest(engine=None):
    engine=engine or get_engine()
    try:
        with engine.connect() as c:
            ts=c.execute(text("SELECT MAX(timestamp) FROM market_snapshots")).scalar()
            if not ts:return pd.DataFrame()
            return pd.read_sql(text("SELECT * FROM market_snapshots WHERE timestamp=:ts"),c,params={"ts":ts})
    except Exception:return pd.DataFrame()
def database_health(engine=None):
    try:
        with (engine or get_engine()).connect() as c:
            n=c.execute(text("SELECT COUNT(*) FROM market_snapshots")).scalar_one()
        return {"database":"connected","stored_records":int(n)}
    except Exception as e:return {"database":"not initialized","stored_records":0,"detail":str(e)[:150]}
