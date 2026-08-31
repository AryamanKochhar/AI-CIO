# Notification Architecture — AI-CIO

## MVP: email only

```text
NotificationService → EmailProvider
  ├── LogEmailProvider (development)
  └── SMTPEmailProvider (production)
```

## Models

- `user_alerts` — alert intent per user
- `notification_deliveries` — delivery audit trail

## Email safety

Forbidden phrases validated before send: `buy now`, `sell now`, `guaranteed`, `risk-free`, etc.

Body generated from structured analysis — not free-form LLM-only output.

## Configuration

`EMAIL_PROVIDER=log|smtp`, `SMTP_*`, `EMAIL_FROM`, `NOTIFICATION_EMAIL` (development/test override)

Development log format:

```text
[EMAIL] To: <recipient> | Subject: ... | Status: generated | body_len=...
```

See `docs/litellm-integration.md` for analysis → email flow.
