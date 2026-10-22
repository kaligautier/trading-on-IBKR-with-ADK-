"""Consultation failures, independent of HTTP status codes and storage drivers."""


class ConsultationError(Exception):
    """Base failure exposed by a consultation use case."""


class AnalysisNotFoundError(ConsultationError):
    """The requested analysis does not exist."""


class InvalidStoredAnalysisError(ConsultationError, ValueError):
    """Persisted financial data violates the read contract."""


class StoreConfigurationError(ConsultationError):
    """The reader schema or effective permissions are incompatible."""


class StoreUnavailableError(ConsultationError):
    """The analysis store is temporarily unavailable."""
