"""
Payments - Provider Abstraction.

Payment gateway provider interface and registry.
All gateway interactions go through this layer.
"""
from .base import BasePaymentProvider
from .fake import FakePaymentProvider
from .registry import get_provider

__all__ = ["BasePaymentProvider", "FakePaymentProvider", "get_provider"]
