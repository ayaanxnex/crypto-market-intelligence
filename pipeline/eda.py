from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from .load import get_engine,read_latest
def generate_charts(folder="eda_output"):
    out=Path(folder);out.mkdir(exist_ok=True,parents=True);df=read_latest(get_engine())
    if df.empty:raise RuntimeError("Run python -m pipeline.run first")
    sns.set_theme(style="whitegrid"); files=[]
    v=df.nlargest(10,"volatility_pct").sort_values("volatility_pct")
    fig,ax=plt.subplots(figsize=(9,5));sns.barplot(data=v,x="volatility_pct",y="symbol",ax=ax);ax.set(title="Top 10 Most Volatile Cryptos",xlabel="Volatility %",ylabel="");fig.tight_layout()
    p=out/"top_volatility.png";fig.savefig(p,dpi=140);plt.close(fig);files.append(str(p))
    fig,ax=plt.subplots(figsize=(8,5));sns.scatterplot(data=df,x="market_cap",y="total_volume",hue="volatility_pct",ax=ax,legend=False);ax.set_xscale("log");ax.set_yscale("log");ax.set(title="Trading Volume vs Market Cap");fig.tight_layout()
    p=out/"volume_vs_market_cap.png";fig.savefig(p,dpi=140);plt.close(fig);files.append(str(p))
    change=df.price_change_percentage_24h.fillna(0);s=pd.Series({"Gainers":int((change>0).sum()),"Losers":int((change<0).sum()),"Flat":int((change==0).sum())})
    fig,ax=plt.subplots(figsize=(7,4));s.plot(kind="bar",ax=ax);ax.set(title="Market Sentiment",ylabel="Number of coins");fig.tight_layout()
    p=out/"market_sentiment.png";fig.savefig(p,dpi=140);plt.close(fig);files.append(str(p));return files
if __name__=="__main__": print("\n".join(generate_charts()))
