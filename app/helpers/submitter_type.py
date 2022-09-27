from enum import Enum


class SubmitterType(str, Enum):
    EMPLOYEE = "employee"
    ADMIN = "admin"
    __description__ = """
Enumération des valeurs suivantes.
- "employee" : salarié
- "admin" : gestionnaire
"""
