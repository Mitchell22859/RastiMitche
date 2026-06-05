# Payment Gateway — Next Steps (P4 Reference)

This document describes the current payment architecture and what is needed
before real Shaparak (Bank Shaparak) split settlement can be activated.

---

## Current Architecture (as of P4)

### Models

| Model | Location | Purpose |
|-------|----------|---------|
| `PaymentGateway` | `apps/payments/models.py` | Company's gateway config (type, merchant_id, api_key, callback_url) |
| `Payment` | `apps/payments/models.py` | Transaction record: INITIATED → PENDING → PAID / FAILED |
| `PaymentAttempt` | `apps/payments/models.py` | Per-attempt log (redirect, verification, errors) |
| `PaymentSplitSnapshot` | `apps/payouts/models.py` | Immutable audit record of split decision at payment time |

### Services

| Service | File | What it does |
|---------|------|-------------|
| `PaymentStartService.start()` | `apps/payments/services.py` | Creates Payment + Attempt, calls provider, returns redirect URL |
| `PaymentVerifyService.verify()` | `apps/payments/services.py` | Verifies with provider, marks Invoice PAID, creates ledger entries + split snapshot |
| `PaymentCallbackService.handle_callback()` | `apps/payments/services.py` | Entry point for gateway callbacks |
| `PaymentSplitDecisionService.compute()` | `apps/payouts/services_split.py` | Pure calculation — returns split decision dict, no DB write |
| `PaymentSplitDecisionService.create_snapshot()` | `apps/payouts/services_split.py` | Idempotent snapshot persist |
| `TechnicianLedgerService` | `apps/payouts/services.py` | All ledger writes |

### Provider Abstraction

```
apps/payments/providers/
├── base.py        # BasePaymentProvider (ABC), PaymentRequest, PaymentResponse, VerificationRequest, VerificationResponse
├── fake.py        # FakePaymentProvider — always succeeds (for testing)
├── registry.py    # _PROVIDER_MAP: GatewayType → ProviderClass, get_provider(), register_provider()
└── __init__.py
```

Adding a new provider requires only:
1. Implement `BasePaymentProvider` (two methods: `initiate_payment`, `verify_payment`)
2. Register in `registry.py`: `_PROVIDER_MAP[GatewayType.ZARINPAL] = ZarinPalProvider`

No changes to `PaymentStartService` or `PaymentVerifyService` are needed.

---

## Where to Implement Real Gateway Integration

### 1. Initiation (`PaymentStartService.start`)

The existing flow is already correct. When the provider is real (not FAKE),
`initiate_payment(request)` must:
- Call the PSP API (e.g., ZarinPal `/pg/v4/payment/request.json`)
- Return `PaymentResponse(success=True, reference_id=authority, redirect_url=...)`

The `PaymentStartService` will automatically:
- Store `reference_id` on `Payment`
- Set `payment.status = PENDING`
- Return `redirect_url` to the view

### 2. Callback / Verification (`PaymentVerifyService.verify`)

When the PSP redirects back (with `Authority` and `Status` params):
- `PaymentCallbackService.handle_callback()` finds the `Payment` by `reference_id`
- `PaymentVerifyService.verify()` calls `provider.verify_payment(VerificationRequest(...))`
- The provider must call PSP verify API (e.g., ZarinPal `/pg/v4/payment/verify.json`)
- On success: `Payment` → PAID, `Invoice` → PAID, ledger entries created, split snapshot created

### 3. Split Settlement (future P5+)

The `PaymentSplitSnapshot` already records whether split is possible at verify time.
When `should_split_with_technician=True`:
- `technician_sub_merchant_id_snapshot` contains the PSP sub-merchant ID
- `technician_direct_amount` is the amount to route directly to technician

For real Shaparak split, the PSP API call during `initiate_payment` must include
split routing parameters (varies by PSP — see below).

---

## What Is Still Missing Before Shaparak Split

| Item | Status | Notes |
|------|--------|-------|
| Real PSP provider class (ZarinPal/IDPay/etc.) | ❌ Not implemented | Implement `BasePaymentProvider` subclass |
| Sandbox / production mode flag | ❌ Not on model | Add `is_sandbox` bool to `PaymentGateway` |
| Split routing in `initiate_payment` | ❌ Not implemented | PSP-specific — see below |
| `sub_merchant_id` per technician | ✅ Exists on `Technician.sub_merchant_id` | Set by platform owner in P3 UI |
| Split snapshot audit | ✅ `PaymentSplitSnapshot` | Written at verify time |
| Ledger credit for technician wage | ✅ `TechnicianLedgerEntry` | Written after each paid invoice |

---

## Data Required from PSP Before Integration

### For Any PSP

| Data | Where to store |
|------|---------------|
| `merchant_id` | `PaymentGateway.merchant_id` (already exists) |
| `api_key` | `PaymentGateway.api_key` (already exists) |
| Callback URL | `PaymentGateway.callback_url` (already exists) |
| Sandbox flag | Add `is_sandbox = BooleanField(default=True)` to `PaymentGateway` |

### For Shaparak Split (Sub-Merchant)

| Data | Where to store |
|------|---------------|
| Technician sub-merchant/payer ID | `Technician.sub_merchant_id` (already exists) |
| Split settlement API endpoint | Provider implementation |
| Split API format | Varies: ZarinPal uses `wages[]`, IDPay uses `wagePerson[]` |
| Settlement reporting API | Provider-specific, for reconciliation |

### ZarinPal Specific

```
POST /pg/v4/payment/request.json
{
  "merchant_id": "...",
  "amount": 500000,
  "callback_url": "...",
  "wages": [
    {"iban": "IRxxxxxxxxxxxxxxxxxxxxxxxx", "amount": 100000, "description": "tech wage"}
  ]
}
```

Verification: `POST /pg/v4/payment/verify.json` with `authority` + `amount`.

### IDPay Specific

```
POST /v1/payment
Headers: X-API-KEY, X-SANDBOX

Body: { "order_id": ..., "amount": ..., "callback": ..., "wagePerson": [...] }
```

---

## How PaymentSplitSnapshot Is Used in Split Flow

```
1. Customer pays → PaymentStartService.start()
   ├─ If SPLIT_WITH_TECHNICIAN + tech verified + sub_merchant_id:
   │   PSP split routing included in initiate_payment request (P5+)
   └─ Otherwise: full amount to company account

2. PSP callback → PaymentVerifyService.verify()
   ├─ provider.verify_payment() confirms with PSP
   ├─ InvoiceMarkPaidService.mark_paid() → snapshot settled amounts
   ├─ PaymentSplitDecisionService.create_snapshot() → immutable audit record
   └─ TechnicianLedgerService.create_invoice_entries() → ledger credit/debit
```

The split snapshot is written *after* verification, as an immutable audit trail
of the decision. The actual PSP routing (when implemented) happens at initiation.

---

## Provider Skeleton for Future Reference

```python
# apps/payments/providers/zarinpal.py

import requests
from .base import BasePaymentProvider, PaymentRequest, PaymentResponse, VerificationRequest, VerificationResponse


class ZarinPalProvider(BasePaymentProvider):
    BASE_URL = "https://api.zarinpal.com/pg/v4/payment"
    SANDBOX_URL = "https://sandbox.zarinpal.com/pg/v4/payment"

    def __init__(self, *, merchant_id: str = "", api_key: str = "", is_sandbox: bool = False, **kwargs):
        super().__init__(merchant_id=merchant_id, api_key=api_key)
        self.base_url = self.SANDBOX_URL if is_sandbox else self.BASE_URL

    def initiate_payment(self, request: PaymentRequest) -> PaymentResponse:
        # TODO: implement — call {base_url}/request.json
        # Include wages[] for split if split_params provided
        raise NotImplementedError("ZarinPal initiation not yet implemented.")

    def verify_payment(self, request: VerificationRequest) -> VerificationResponse:
        # TODO: implement — call {base_url}/verify.json
        raise NotImplementedError("ZarinPal verification not yet implemented.")


# Register when ready:
# from apps.payments.providers.registry import register_provider
# from apps.payments.models import PaymentGateway
# register_provider(PaymentGateway.GatewayType.ZARINPAL, ZarinPalProvider)
```

---

## Checklist Before Going Live

- [ ] Implement `ZarinPalProvider` (or chosen PSP) with real API calls
- [ ] Add `is_sandbox` to `PaymentGateway` model + migration
- [ ] Test initiation + callback + verification in sandbox
- [ ] Confirm `PaymentSplitSnapshot.should_split_with_technician` logic with PSP split params
- [ ] Ensure all technicians who need split have `sub_merchant_id` set via platform owner UI
- [ ] Verify callback URL is publicly accessible (not localhost)
- [ ] Add idempotency check on verify to prevent double-marking on retried callbacks
- [ ] Enable HTTPS on callback endpoint
- [ ] Confirm PSP settlement reporting is available for reconciliation
