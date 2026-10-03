"""Authoritative Verification Adapters Package."""
from sangyan.verification.adapters.base import ADAPTER_STATUSES, AdapterResult, VerificationAdapter
from sangyan.verification.adapters.circulars import CircularsVerificationAdapter
from sangyan.verification.adapters.mca import MCAVerificationAdapter
from sangyan.verification.adapters.official_domains import OfficialDomainsVerificationAdapter
from sangyan.verification.adapters.sebi import SEBIVerificationAdapter

__all__ = [
    "ADAPTER_STATUSES",
    "AdapterResult",
    "VerificationAdapter",
    "SEBIVerificationAdapter",
    "MCAVerificationAdapter",
    "CircularsVerificationAdapter",
    "OfficialDomainsVerificationAdapter",
]
