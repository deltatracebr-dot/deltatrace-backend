from datetime import datetime

from fastapi import APIRouter
from .schemas import IPScanRequest, IPScanResult

router = APIRouter()


@router.post("/ip", response_model=IPScanResult)
def lookup_ip(payload: IPScanRequest):
    # TODO: integrar com serviço real (ipinfo, etc.)
    # Mock inicial só pra testar fluxo front <-> back
    return IPScanResult(
        ip=str(payload.ip),
        country="BR",
        org="Delta Trace Mock Network",
        asn="AS0000",
        created_at=datetime.utcnow(),
    )
