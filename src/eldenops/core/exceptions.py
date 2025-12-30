"""Custom exceptions for EldenOps."""

from __future__ import annotations

from typing import Any, Optional


class EldenOpsError(Exception):
    """Base exception for EldenOps."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ConfigurationError(EldenOpsError):
    """Configuration related errors."""

    pass


class AuthenticationError(EldenOpsError):
    """Authentication failures."""

    pass


class AuthorizationError(EldenOpsError):
    """Authorization/permission failures."""

    pass


class TenantNotFoundError(EldenOpsError):
    """Tenant not found."""

    pass


class UserNotFoundError(EldenOpsError):
    """User not found."""

    pass


class AIProviderError(EldenOpsError):
    """AI provider errors."""

    pass


class RateLimitError(AIProviderError):
    """Rate limit exceeded."""

    def __init__(
        self, message: str, retry_after: Optional[int] = None, **kwargs: Any
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class GitHubIntegrationError(EldenOpsError):
    """GitHub API errors."""

    pass


class DiscordIntegrationError(EldenOpsError):
    """Discord API errors."""

    pass


class ReportGenerationError(EldenOpsError):
    """Report generation failures."""

    pass


class ValidationError(EldenOpsError):
    """Data validation errors."""

    pass
