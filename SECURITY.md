# Security Notes (TeacherTools)

## Admin Credentials
Do not store real usernames/passwords in this repository.

Create or rotate admin password with:

```bash
python scripts/set_admin_password.py --username admin --generate
```

Or set an explicit password:

```bash
python scripts/set_admin_password.py --username admin --password "<new-strong-password>"
```

## Environment Variables
Keep secrets only in local `.env` or deployment secrets manager.

Required/important secrets:
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `TELEGRAM_BOT_TOKEN`
- `GITHUB_WEBHOOK_SECRET`
- `WEBDAV_LOGIN`
- `WEBDAV_PASSWORD`
- `OPENAI_API_KEY` (if AI features are enabled)

## Rotation Policy
- Rotate credentials immediately after any accidental commit.
- Rotate on a regular schedule.
- Never print secrets in logs.

## Recommended Hardening
- Enable branch protection.
- Add secret scanning in CI (for example, gitleaks).
- Restrict access to production environment variables.
