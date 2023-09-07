from app import MobilicError
from abc import ABC


class IntegrityVerificationError(MobilicError, ABC):
    http_status_code = 200


class InvalidXlsxFormat(IntegrityVerificationError):
    code = "INVALID_FORMAT"


class MissingSignature(IntegrityVerificationError):
    code = "MISSING_SIGNATURE"


class SignatureDoesNotMatch(IntegrityVerificationError):
    code = "SIGNATURE_DOES_NOT_MATCH"


class UnavailableService(IntegrityVerificationError):
    code = "UNAVAILABLE"
