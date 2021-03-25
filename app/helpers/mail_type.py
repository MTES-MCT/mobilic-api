from enum import Enum


class EmailType(str, Enum):
    ACCOUNT_ACTIVATION = "account_activation"
    COMPANY_CREATION = "company_creation"
    EMPLOYMENT_VALIDATION = "employment_validation_confirmation"
    INVITATION = "invitation"
    MISSION_CHANGES_WARNING = "mission_changes_warning"
    RESET_PASSWORD = "reset_password"
    WORKER_ONBOARDING_FIRST_INFO = "worker_onboarding_first_info"
    WORKER_ONBOARDING_SECOND_INFO = "worker_onboarding_second_info"
    MANAGER_ONBOARDING_FIRST_INFO = "manager_onboarding_first_info"
    MANAGER_ONBOARDING_SECOND_INFO = "manager_onboarding_second_info"
