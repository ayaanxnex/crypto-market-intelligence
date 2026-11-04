import os
import requests

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


COINGECKO_URL = "https://api.coingecko.com/api/v3"


def get_history(coin_id, days):
    allowed_days = {1, 7, 30, 90, 365}

    if not coin_id or len(coin_id) > 100:
        raise ValueError("Invalid coin ID")

    if days not in allowed_days:
        raise ValueError("Invalid number of days")

    headers = {
        "accept": "application/json"
    }

    api_key = os.getenv("COINGECKO_API_KEY")
    if api_key:
        headers["x-cg-demo-api-key"] = api_key

    response = requests.get(
        f"{COINGECKO_URL}/coins/{coin_id}/market_chart",
        params={
            "vs_currency": "usd",
            "days": days
        },
        headers=headers,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    return {
        "coin_id": coin_id,
        "days": days,
        "prices": data.get("prices", [])
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            params = parse_qs(urlparse(self.path).query)

            coin_id = params.get("id", [""])[0]
            days_value = params.get("days", ["1"])[0]

            try:
                days = int(days_value)
            except ValueError:
                raise ValueError("Days must be a number")

            result = get_history(coin_id, days)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            import json
            self.wfile.write(json.dumps(result).encode("utf-8"))

        except ValueError as e:
            self.send_error(400, str(e))

        except requests.RequestException:
            self.send_error(502, "CoinGecko historical data is temporarily unavailable")

        except Exception:
            self.send_error(500, "Internal server error")