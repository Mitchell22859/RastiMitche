"""
SMS - Provider Abstraction.

SMS gateway provider interface and registry.
"""
from .base import BaseSMSProvider
from .fake import FakeSMSProvider
from .registry import get_sms_provider

__all__ = ["BaseSMSProvider", "FakeSMSProvider", "get_sms_provider"]
