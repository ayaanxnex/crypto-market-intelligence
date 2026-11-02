import logging
from pydantic import BaseModel, ConfigDict, Field, field_validator, ValidationError
log=logging.getLogger(__name__)
class CryptoSchema(BaseModel):
    model_config=ConfigDict(extra="ignore")
    id:str=Field(min_length=1); symbol:str=Field(min_length=1); name:str=Field(min_length=1)
    current_price:float=Field(ge=0); high_24h:float=Field(ge=0); low_24h:float=Field(ge=0)
    total_volume:float=Field(ge=0); market_cap:float=Field(ge=0)
    price_change_percentage_24h:float|None=None; market_cap_rank:int|None=None
    @field_validator("symbol")
    @classmethod
    def upper(cls,v): return v.strip().upper()
    @field_validator("id","name")
    @classmethod
    def nonblank(cls,v):
        v=v.strip()
        if not v: raise ValueError("must not be blank")
        return v
def validate_markets(rows):
    good=[]; rejected=[]
    for row in rows:
        try: good.append(CryptoSchema.model_validate(row))
        except (ValidationError,TypeError) as e:
            rejected.append({"id":row.get("id","unknown"),"error":str(e)})
            log.warning("Dropping invalid record %s",row.get("id","unknown"))
    return good,rejected
