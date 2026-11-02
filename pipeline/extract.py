import os, requests
URL = "https://api.coingecko.com/api/v3/coins/markets"
def extract_markets(per_page=50):
    headers = {"User-Agent":"Blockscope-P4AI/1.0"}
    if os.getenv("COINGECKO_API_KEY"):
        headers["x-cg-demo-api-key"] = os.environ["COINGECKO_API_KEY"]
    r = requests.get(URL, params={"vs_currency":"usd","order":"market_cap_desc","per_page":min(50,max(1,per_page)),"page":1,"sparkline":"false"}, headers=headers, timeout=(3,10))
    r.raise_for_status()
    data = r.json()
    if not isinstance(data,list): raise ValueError("Unexpected CoinGecko response")
    return data
