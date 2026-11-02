# Blockscope — Crypto Market Intelligence

P4AI semester project: ETL + EDA dashboard using CoinGecko, Requests, Pydantic, Pandas, SQLAlchemy and SQLite locally / PostgreSQL on Vercel.

## Run locally
Python 3.11+:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pipeline.run
python -m pipeline.eda
```
For the web UI/API locally, install Vercel CLI (`npm i -g vercel`) and run `vercel dev`.

## Deploy
1. Unzip and push this folder to a new GitHub repository.
2. In Vercel, Add New → Project → import that repository. Framework preset: Other.
3. Create a free PostgreSQL database at Neon (or another provider).
4. Vercel → Project → Settings → Environment Variables: add `DATABASE_URL` with the provider's PostgreSQL connection string. Optional: `COINGECKO_API_KEY`; `VOLATILITY_THRESHOLD=10`.
5. Deploy and open your Vercel URL. Click **Refresh pipeline**.
6. Never commit `.env` or database credentials.

**Important:** Vercel serverless storage is ephemeral; SQLite files are not durable or shared across function instances. This project uses SQLite locally and PostgreSQL in deployment, through the same SQLAlchemy loader.

## Endpoints
`GET /api/market`, `POST /api/refresh`, `GET /api/health`.
CoinGecko public API has rate limits; avoid repeated refreshes. The “Simulate shock” button is a demo and does not send a real webhook.
