"""
Sends a completion notice right after a Tech Vector rebuild actually runs
(see .github/workflows/rebuild-data.yml's "send-completion-notice" job,
which only calls this script once the "rebuild" job both fired - it wasn't
one of the ~51/56 non-rebuild weekly no-op runs - and succeeded end to end).
This script itself doesn't check any of that; it just sends one email when
invoked, so all failure-vs-success logic lives in the workflow, not here.

Confirms the dashboard has been refreshed and reminds the research team to
write an update in Briefly (the internal tool identified during this
project's automation planning). No Briefly URL is included - hyperlinking
to it would mean guessing a URL, which isn't safe to do; it's named in
plain text only. If a real Briefly URL is provided later, add it to
BRIEFLY_URL below and the email body will pick it up automatically.

AUTH
----
Uses the same Zoho Self Client OAuth2 stack (and the SAME 3 credentials -
ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET / ZOHO_REFRESH_TOKEN) as
automated_fetch_zoho_abns.py and automated_send_reminder_email.py - see
automated_send_reminder_email.py's docstring for the caveat that this
assumes one Self Client was authorized for both a CRM read scope and a
Mail send scope together.

The auth/send helpers below are intentionally a near-duplicate of
automated_send_reminder_email.py rather than a shared module - every
script in this directory is designed to be fully standalone (see
automated_fetch_all_data.py's docstring), and this preserves that property.

ONE-TIME SETUP REQUIRED BEFORE THIS WORKS
------------------------------------------
    ZOHO_MAIL_ACCOUNT_ID - same numeric Zoho Mail "accountId" used in
                           automated_send_reminder_email.py - same
                           mailbox, so the same value goes in both files.
    FROM_ADDRESS         - same sending mailbox address, in both files.

USAGE
-----
    python3 automated_send_completion_email.py
"""

import os
import sys
from datetime import datetime, timezone

import requests

ZOHO_ACCOUNTS_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"
ZOHO_MAIL_SEND_URL_TEMPLATE = "https://mail.zoho.com/api/accounts/{account_id}/messages"

# ---------------------------------------------------------------------------
# ONE-TIME SETUP: fill these in once (see docstring above) - same values as
# automated_send_reminder_email.py, since it's the same sending mailbox.
# ---------------------------------------------------------------------------
ZOHO_MAIL_ACCOUNT_ID = "REPLACE_ME"  # TODO: one-time setup - numeric Zoho Mail accountId (GET https://mail.zoho.com/api/accounts)
FROM_ADDRESS = "REPLACE_ME@techcouncil.com.au"  # TODO: one-time setup - sending mailbox address matching the account above
# ---------------------------------------------------------------------------

TO_ADDRESS = "research@techcouncil.com.au"

# No confirmed URL for Briefly yet - fill this in once known and the email
# body below will link to it instead of just naming it in plain text.
BRIEFLY_URL = None

DASHBOARD_URL = "https://techcouncil.com.au/tech-vector"


def get_access_token(session: requests.Session, client_id: str, client_secret: str, refresh_token: str) -> tuple:
    """Same token exchange as automated_fetch_zoho_abns.py /
    automated_send_reminder_email.py."""
    resp = session.post(
        ZOHO_ACCOUNTS_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "access_token" not in payload:
        raise RuntimeError(f"Unexpected token response from Zoho (missing access_token): {payload}")
    return payload["access_token"], payload.get("api_domain")


def build_email() -> tuple:
    """Returns (subject, html_content)."""
    today = datetime.now(timezone.utc).date()

    subject = f"Tech Vector dashboard updated ({today.isoformat()}) - please write an update in Briefly"

    briefly_mention = (
        f'<a href="{BRIEFLY_URL}">Briefly</a>' if BRIEFLY_URL else "<strong>Briefly</strong>"
    )
    content = (
        f"<p>Hi team,</p>"
        f"<p>The Tech Vector dashboard just finished its automated data rebuild "
        f"({today.isoformat()}) - the charts at "
        f'<a href="{DASHBOARD_URL}">{DASHBOARD_URL}</a> now reflect the latest data.</p>'
        f"<p>Please write an update in {briefly_mention} summarizing what changed this cycle.</p>"
        f"<p style=\"color:#888;font-size:12px;\">Automated notice from tca-research/tech_vector's "
        f"GitHub Actions workflow (.github/workflows/rebuild-data.yml, "
        f"scripts/automated_send_completion_email.py).</p>"
    )
    return subject, content


def send_email(session: requests.Session, access_token: str, subject: str, content: str) -> None:
    url = ZOHO_MAIL_SEND_URL_TEMPLATE.format(account_id=ZOHO_MAIL_ACCOUNT_ID)
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json",
    }
    body = {
        "fromAddress": FROM_ADDRESS,
        "toAddress": TO_ADDRESS,
        "subject": subject,
        "content": content,
        "mailFormat": "html",
    }
    resp = session.post(url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()


def main():
    if ZOHO_MAIL_ACCOUNT_ID == "REPLACE_ME" or FROM_ADDRESS.startswith("REPLACE_ME"):
        print(
            "Error: ZOHO_MAIL_ACCOUNT_ID and/or FROM_ADDRESS are still unset placeholders - "
            "see this script's docstring for the one-time setup steps.",
            file=sys.stderr,
        )
        sys.exit(1)

    client_id = os.environ.get("ZOHO_CLIENT_ID")
    client_secret = os.environ.get("ZOHO_CLIENT_SECRET")
    refresh_token = os.environ.get("ZOHO_REFRESH_TOKEN")
    missing_env = [
        name
        for name, value in [
            ("ZOHO_CLIENT_ID", client_id),
            ("ZOHO_CLIENT_SECRET", client_secret),
            ("ZOHO_REFRESH_TOKEN", refresh_token),
        ]
        if not value
    ]
    if missing_env:
        print(
            f"Error: missing required environment variable(s): {', '.join(missing_env)}. "
            f"Set these (e.g. as GitHub Actions secrets) before running this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; zoho-completion-email-script/1.0)"})

    print("Requesting a Zoho access token ...", file=sys.stderr)
    try:
        access_token, _api_domain = get_access_token(session, client_id, client_secret, refresh_token)
    except requests.HTTPError as e:
        body = e.response.text if e.response is not None else "<no body>"
        print(f"Error: Zoho token request failed: {e}\nResponse body: {body}", file=sys.stderr)
        sys.exit(1)

    subject, content = build_email()
    print(f"Sending completion email to {TO_ADDRESS}: {subject!r}", file=sys.stderr)
    try:
        send_email(session, access_token, subject, content)
    except requests.HTTPError as e:
        body = e.response.text if e.response is not None else "<no body>"
        print(f"Error: Zoho Mail send failed: {e}\nResponse body: {body}", file=sys.stderr)
        sys.exit(1)

    print(f"Completion email sent to {TO_ADDRESS}.")


if __name__ == "__main__":
    main()
