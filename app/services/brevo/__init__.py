"""Brevo services package.

- Data finders: Pure database queries
- API client: All Brevo API interactions in helpers/brevo.py
- Orchestrator: Coordinates data finders and API interactions
"""

from .acquisition_data_finder import (
    AcquisitionDataFinder,
    get_companies_acquisition_data,
)
from .activation_data_finder import (
    ActivationDataFinder,
    get_companies_activation_data,
)
from .orchestrator import (
    BrevoSyncOrchestrator,
    sync_all_funnels,
    sync_dual_pipeline_funnel,
    SyncResult,
)
from .testing import FunnelTester

__all__ = [
    "AcquisitionDataFinder",
    "ActivationDataFinder",
    "get_companies_acquisition_data",
    "get_companies_activation_data",
    "BrevoSyncOrchestrator",
    "sync_all_funnels",
    "sync_dual_pipeline_funnel",
    "SyncResult",
    "FunnelTester",
]
