"""
SMS - Fake SMS Provider.

Used for testing. Simulates SMS sending without external calls.
"""
import uuid

from .base import BaseSMSProvider, SMSSendRequest, SMSSendResponse


class FakeSMSProvider(BaseSMSProvider):
    """
    Fake SMS provider for testing.

    Behavior:
    - If phone starts with "0900" → fails
    - Otherwise → succeeds with a fake message_id
    """

    def send(self, request: SMSSendRequest) -> SMSSendResponse:
        """Simulate SMS sending."""
        if request.phone_number.startswith("0900"):
            return SMSSendResponse(
                success=False,
                error_message="Invalid phone number (test failure).",
            )

        message_id = f"FAKE-{uuid.uuid4().hex[:10]}"
        return SMSSendResponse(
            success=True,
            message_id=message_id,
        )
