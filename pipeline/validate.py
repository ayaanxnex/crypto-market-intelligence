
import logging
import math

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

log = logging.getLogger(__name__)


class CryptoSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    name: str = Field(min_length=1)

    current_price: float = Field(gt=0)
    high_24h: float = Field(ge=0)
    low_24h: float = Field(ge=0)
    total_volume: float = Field(ge=0)
    market_cap: float = Field(ge=0)

    price_change_percentage_24h: float | None = None
    price_change_percentage_1h_in_currency: float | None = None
    price_change_percentage_7d_in_currency: float | None = None
    market_cap_rank: int | None = None
    image: str | None = None
    fully_diluted_valuation: float | None = None
    price_change_24h: float | None = None
    market_cap_change_24h: float | None = None
    market_cap_change_percentage_24h: float | None = None
    circulating_supply: float | None = None
    total_supply: float | None = None
    max_supply: float | None = None
    ath: float | None = None
    ath_change_percentage: float | None = None
    ath_date: str | None = None
    atl: float | None = None
    atl_change_percentage: float | None = None
    atl_date: str | None = None
    last_updated: str | None = None
    sparkline_in_7d: dict | None = None

    @field_validator("symbol")
    @classmethod
    def clean_symbol(cls, value):
        value = value.strip().upper()
        if not value:
            raise ValueError("Symbol cannot be blank")
        return value

    @field_validator("id", "name")
    @classmethod
    def clean_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value

    @field_validator(
        "current_price", "high_24h", "low_24h",
        "total_volume", "market_cap",
        "price_change_percentage_24h",
        "price_change_percentage_1h_in_currency",
        "price_change_percentage_7d_in_currency",
        "fully_diluted_valuation", "price_change_24h",
        "market_cap_change_24h",
        "market_cap_change_percentage_24h",
        "circulating_supply", "total_supply", "max_supply",
        "ath", "ath_change_percentage",
        "atl", "atl_change_percentage",
        mode="before",
    )
    @classmethod
    def check_finite_numbers(cls, value):
        if value is None:
            return value
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError("Must be a valid number")
        if not math.isfinite(number):
            raise ValueError("Number must be finite")
        return number

    @field_validator("high_24h")
    @classmethod
    def check_high_low(cls, value, info):
        low = info.data.get("low_24h")
        if low is not None and value < low:
            raise ValueError("24h high cannot be lower than 24h low")
        return value


def _reason(exc):
    if isinstance(exc, ValidationError):
        errors = exc.errors()
        if errors:
            first = errors[0]
            field = ".".join(str(x) for x in first.get("loc", ())) or "record"
            return f"{field}: {first.get('msg', 'invalid value')}"
    return str(exc)[:150]


def validate_markets(rows):
    good = []
    rejected = []
    seen_ids = set()

    for row in rows:
        row_id = row.get("id", "unknown") if isinstance(row, dict) else "unknown"

        try:
            coin = CryptoSchema.model_validate(row)

            # Duplicate detection
            if coin.id.lower() in seen_ids:
                rejected.append({
                    "id": row_id,
                    "error": "Duplicate coin ID"
                })
                continue

            seen_ids.add(coin.id.lower())
            good.append(coin)

        except (ValidationError, TypeError, ValueError) as exc:
            rejected.append({
                "id": row_id,
                "error": _reason(exc)
            })
            log.warning("Dropping invalid record %s", row_id)

    return good, rejected
