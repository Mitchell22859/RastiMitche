"""
SMS - Base SMS Provider.

Abstract interface that all SMS providers must implement.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SMSSendRequest:
    """Data needed to send an SMS."""
    phone_number: str
    message: str


@dataclass
class SMSSendResponse:
    """Response from SMS provider."""
    success: bool
    message_id: str = ""
    error_message: str = ""


class BaseSMSProvider(ABC):
    """
    Abstract base for SMS providers.

    Implementations:
    - FakeSMSProvider (testing)
    - Future: KavenegarProvider, GhasedakProvider
    """

    def __init__(self, *, api_key: str = "", sender_number: str = "", **kwargs):
        self.api_key = api_key
        self.sender_number = sender_number

    @abstractmethod
    def send(self, request: SMSSendRequest) -> SMSSendResponse:
        """Send an SMS message."""
        ...
