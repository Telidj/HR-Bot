# Teams Integration Guide

This project supports two presentation modes:
- Streamlit user and admin interfaces
- Microsoft Teams chat and admin gateways

## Start Teams Mode
```powershell
powershell -ExecutionPolicy Bypass -File .\run_teams_demo.ps1
```

Local services:
- API: `http://127.0.0.1:8000`
- Teams gateway: `http://127.0.0.1:3978`
- Chat webhook endpoint: `http://127.0.0.1:3978/api/messages/chat`
- Admin webhook endpoint: `http://127.0.0.1:3978/api/messages/admin`

Stop Teams mode:
```powershell
powershell -ExecutionPolicy Bypass -File .\stop_teams_demo.ps1
```

## Expose Public HTTPS Endpoints
Microsoft Teams must call public HTTPS URLs. Use a tunnel such as ngrok or cloudflared and map:
- Public URL 1 -> `http://127.0.0.1:3978/api/messages/chat`
- Public URL 2 -> `http://127.0.0.1:3978/api/messages/admin`

## Configure Teams Outgoing Webhooks
Create two outgoing webhooks in Teams:
- `HR & IT Assistant Chat`
- `HR & IT Assistant Admin`

If webhook signature validation is enabled, configure either:
- `TEAMS_WEBHOOK_SECRET` for a shared secret
- or `TEAMS_CHAT_WEBHOOK_SECRET` and `TEAMS_ADMIN_WEBHOOK_SECRET` for separate secrets

## Minimal `.env` for Teams Mode
```env
API_BASE_URL=http://127.0.0.1:8000
ADMIN_TOKEN=change-me
LOG_USER_TEXT_MODE=masked
# Optional:
# TEAMS_PORT=3978
# TEAMS_TIMEOUT_SEC=90
# TEAMS_WEBHOOK_SECRET=
# TEAMS_ADMIN_ALLOWED_USERS=29:1ABC...,29:1DEF...
```

## Chat Commands
- `help`
- `requests`
- `request <request_id_fragment>`
- `clear`
- Any other message is sent to the assistant

## Admin Commands
Authentication:
- `login <ADMIN_TOKEN>`
- `logout`

Core commands:
- `help`
- `prompt get`
- `prompt set <text>`
- `docs list`
- `docs preview <document_name>`
- `docs upload <file_name> ::: <content>`
- `docs delete <document_name>`
- `index rebuild`
- `logs [limit]`
- `requests [limit] [status <status>] [user <user>] [id <request_id_fragment>]`
- `request get <request_id_fragment>`
- `request update <request_id> <status>`

## Security Notes
- Teams admin access can be restricted to approved user IDs with `TEAMS_ADMIN_ALLOWED_USERS`
- Admin login can be disabled, but that is not recommended even for demo use
- Teams mode is still demo-oriented and does not replace enterprise authentication controls
