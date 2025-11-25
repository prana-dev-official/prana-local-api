class PranaApiClientException(Exception):
    """Base exception for the Prana API client library."""

class PranaApiCommunicationError(PranaApiClientException):
    """Network communication error (e.g., ClientError, TimeoutError)."""

class PranaApiUpdateFailed(PranaApiClientException):
    """HTTP request failed (e.g., status code not 200)."""
    def __init__(self, status: int, message: str = "HTTP error"):
        super().__init__(f"{message} {status}")
        self.status = status