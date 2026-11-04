import logging
from pydantic import BaseModel, ConfigDict, Field, field_validator, ValidationError

log = logging.getLogger(__name__)


class CryptoSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Required fields: a record missing or breaking any of these is rejected.
    id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    name: str = Field(min_length=1)
    current_price: float = Field(ge=0)
    high_24h: float = Field(ge=0)
    low_24h: float = Field(ge=0)
    total_volume: float = Field(ge=0)
    market_cap: float = Field(ge=0)

    # Optional fields: kept when CoinGecko provides them.
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
    def upper(cls, v):
        return v.strip().upper()

    @field_validator("id", "name")
    @classmethod
    def nonblank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


def _reason(exc):
    """Short, groupable rejection reason, e.g. 'market_cap: Input should be a valid number'."""
    if isinstance(exc, ValidationError):
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = ".".join(str(x) for x in first.get("loc", ())) or "record"
            return f"{loc}: {first.get('msg', 'invalid value')}"
    return str(exc)[:150]


def validate_markets(rows):
    good, rejected = [], []
    for row in rows:
        row_id = row.get("id", "unknown") if isinstance(row, dict) else "unknown"
        try:
            good.append(CryptoSchema.model_validate(row))
        except (ValidationError, TypeError) as e:
            rejected.append({"id": row_id, "error": _reason(e)})
            log.warning("Dropping invalid record %s", row_id)
    return good, rejected
