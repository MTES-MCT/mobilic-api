"""
Anonymization services for Mobilic API.

This module provides functionality for anonymizing old data, ensuring compliance
with data protection regulations. Two main anonymization approaches are implemented:

1. Standalone data anonymization (missions, companies, etc.):
   - Data is duplicated to anonymized tables
   - Original data is optionally deleted

2. User anonymization:
   - Users are anonymized in-place by replacing their ID with a negative ID
   - Personal information is removed
"""

from app.services.anonymization.common import AnonymizationManager
from app.services.anonymization.standalone import (
    DataFinder,
    AnonymizationExecutor,
    anonymize_expired_data,
)
from app.services.anonymization.user_related import (
    UserClassifier,
    UserAnonymizer,
    anonymize_users,
)

__all__ = [
    "AnonymizationManager",
    "DataFinder",
    "AnonymizationExecutor",
    "UserClassifier",
    "UserAnonymizer",
    "anonymize_expired_data",
    "anonymize_users",
]
