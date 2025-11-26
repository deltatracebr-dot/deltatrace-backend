from pydantic import BaseModel, IPvAnyAddress
from datetime import datetime


class IPScanRequest(BaseModel):
    ip: IPvAnyAddress


class IPScanResult(BaseModel):
    ip: str
    country: str | None = None
    org: str | None = None
    asn: str | None = None
    created_at: datetime
