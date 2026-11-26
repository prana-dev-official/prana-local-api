"""Exceptions raised by the Prana local API client.

Hierarchy::

    PranaApiClientException
    └── UpdateFailed                    any failed request to the device
        ├── PranaApiCommunicationError  network error or timeout
        ├── PranaApiUpdateFailed        device answered with a non-200 status
        └── PranaApiInvalidResponse     device answered with an unexpected payload

``ValueError`` is raised (before any request is sent) for invalid arguments.
"""

from __future__ import annotations


class PranaApiClientException(Exception):
    """Base exception for the Prana API client library."""


class UpdateFailed(PranaApiClientException):
    """A request to the device failed.

    Common base of all request errors, so ``except UpdateFailed`` keeps catching
    every failure of :meth:`PranaLocalApiClient.get_state` like in earlier versions.
    """


class PranaApiCommunicationError(UpdateFailed):
    """The device could not be reached (connection error or timeout)."""


class PranaApiUpdateFailed(UpdateFailed):
    """The device answered with a non-200 HTTP status."""

    def __init__(self, status: int, message: str = "HTTP error") -> None:
        """Initialize with the HTTP status returned by the device."""
        super().__init__(f"{message} {status}")
        self.status = status


class PranaApiInvalidResponse(UpdateFailed):
    """The device answered with a payload that could not be understood."""
