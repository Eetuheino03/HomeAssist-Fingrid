"""Exceptions for the Fingrid Easy Setup integration."""

from homeassistant.exceptions import HomeAssistantError

class FingridApiClientError(HomeAssistantError):
    """Base class for Fingrid API client errors."""

class FingridApiAuthError(FingridApiClientError):
    """Exception for Fingrid API authentication errors (401, 403)."""

class FingridApiRateLimitError(FingridApiClientError):
    """Exception for Fingrid API rate limit errors (429)."""

class FingridApiError(FingridApiClientError):
    """Exception for other Fingrid API errors."""