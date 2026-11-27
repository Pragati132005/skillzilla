"""Typed errors so the API layer can map every failure to a clean HTTP status."""
from __future__ import annotations

from typing import Any, Dict, Optional


class TalentCheckError(Exception):
    code = "talent_check_error"
    http_status = 500

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            out["details"] = self.details
        return out


class CompanyDataError(TalentCheckError):
    code = "company_data_error"
    http_status = 503


class SupabaseError(CompanyDataError):
    code = "supabase_error"


class CompanyNotFoundError(TalentCheckError):
    code = "company_not_found"
    http_status = 404


class AmbiguousCompanyError(TalentCheckError):
    code = "ambiguous_company"
    http_status = 409


class ProfileError(TalentCheckError):
    code = "invalid_profile"
    http_status = 422


class RequestError(TalentCheckError):
    code = "bad_request"
    http_status = 400


class PayloadTooLargeError(RequestError):
    code = "payload_too_large"
    http_status = 413
