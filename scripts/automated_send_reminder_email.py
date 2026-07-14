"""
Sends a reminder email exactly 7 days before each 8-week Tech Vector
rebuild cycle (see .github/workflows/rebuild-data.yml's "send-reminder"
job, which computes the 7-days-before gate and calls this script - this
script itself doesn't know or care about the cycle math, it just sends
one email when invoked).

Lists the manually-curated data sources someone should sanity-check before
the next automated rebuild runs. After scripts/automated_fetch_zoho_abns.py
automated the Tech Council member ABN pull, this is down to 2 sources:
    - Headline gauge metrics   (scripts/MANUAL_DATA_PULL_INSTRUCTIONS_HEADLINE_METRICS.md)
    - ABS TableBuilder exports (scripts/MANUAL_DATA_PULL_INSTRUCTIONS_TABLEBUILDER_UPLOAD.md)

AUTH
----
Uses the same Zoho Self Client OAuth2 stack (and the SAME 3 credentials -
ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET / ZOHO_REFRESH_TOKEN) as
automated_fetch_zoho_abns.py - this ASSUMES the one-time Self Client setup
requested BOTH a CRM read scope and a Mail send scope up front (Zoho lets
one Self Client grant span multiple products' scopes in a single
authorization, e.g. "ZohoCRM.modules.accounts.READ
ZohoMail.messages.CREATE"). This assumption is UNVERIFIED against an actual
Self Client setup - flagging it explicitly. If it turns out to be wrong
(e.g. your Zoho admin issued two separate Self Clients), this script would
need its own ZOHO_MAIL_CLIENT_ID/SECRET/REFRESH_TOKEN env vars instead.

The auth helper below is intentionally a near-duplicate of the one in
automated_fetch_zoho_abns.py rather than an imported shared module - every
script in this directory is designed to be fully standalone (see
automated_fetch_all_data.py's docstring), and this preserves that property.

ONE-TIME SETUP REQUIRED BEFORE THIS WORKS
------------------------------------------
    ZOHO_MAIL_ACCOUNT_ID - the numeric Zoho Mail "accountId" for the
                           mailbox that should send this email. Obtain
                           once via:
                               GET https://mail.zoho.com/api/accounts
                               Authorization: Zoho-oauthtoken {access_token}
                           and hardcode the "accountId" of the desired
                           mailbox below - this is fixed once known, not
                           something to look up on every run.
    FROM_ADDRESS         - the sending mailbox's address, must belong to
                           the account above.

USAGE
-----
    python3 automated_send_reminder_email.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import requests

ZOHO_ACCOUNTS_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"
ZOHO_MAIL_SEND_URL_TEMPLATE = "https://mail.zoho.com/api/accounts/{account_id}/messages"

# ---------------------------------------------------------------------------
# ONE-TIME SETUP: fill these in once (see docstring above), then they never
# need to change again.
# ---------------------------------------------------------------------------
ZOHO_MAIL_ACCOUNT_ID = "REPLACE_ME"  # TODO: one-time setup - numeric Zoho Mail accountId (GET https://mail.zoho.com/api/accounts)
FROM_ADDRESS = "REPLACE_ME@techcouncil.com.au"  # TODO: one-time setup - sending mailbox address matching the account above
# ---------------------------------------------------------------------------

TO_ADDRESS = "research@techcouncil.com.au"

REPO_BLOB_BASE = "https://github.com/tca-research/tech_vector/blob/main"

MANUAL_SOURCES = [
    {
        "name": "Headline gauge metrics",
        "detail": "Tech Investment / Tech Sector GDP figures, and the Tech Jobs gauge's raw source",
        "doc": "scripts/MANUAL_DATA_PULL_INSTRUCTIONS_HEADLINE_METRICS.md",
    },
    {
        "name": "ABS TableBuilder exports",
        "detail": "tech-roles-by-subsector breakdown",
        "doc": "scripts/MANUAL_DATA_PULL_INSTRUCTIONS_TABLEBUILDER_UPLOAD.md",
    },
]


def get_access_token(session: requests.Session, client_id: str, client_secret: str, refresh_token: str) -> tuple:
    """Same token exchange as automated_fetch_zoho_abns.py - see that
    script's docstring for why api_domain matters for CRM calls. This
    script only needs the access_token itself (Zoho Mail's endpoint is
    always mail.zoho.com regardless of data center, unlike CRM's
    api_domain), but returns api_domain too for consistency/debuggability."""
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
    rebuild_date = today + timedelta(days=7)

    subject = f"Tech Vector rebuild in 7 days ({rebuild_date.isoformat()}) - 2 manual data sources to check"

    items_html = "".join(
        f'<li><strong>{s["name"]}</strong> ({s["detail"]}) - see '
        f'<a href="{REPO_BLOB_BASE}/{s["doc"]}">{s["doc"]}</a></li>'
        for s in MANUAL_SOURCES
    )
    content = (
        f"<p>Hi team,</p>"
        f"<p>The Tech Vector dashboard's next automated data rebuild is scheduled for "
        f"<strong>{rebuild_date.isoformat()}</strong> (7 days from today, {today.isoformat()}).</p>"
        f"<p>Before then, please check these {len(MANUAL_SOURCES)} manually-curated data "
        f"sources are current:</p>"
        f"<ul>{items_html}</ul>"
        f"<p>If they're already up to date, no action needed - the rebuild will just use the "
        f"existing files.</p>"
        f"<p style=\"color:#888;font-size:12px;\">Automated reminder from tca-research/tech_vector's "
        f"GitHub Actions workflow (.github/workflows/rebuild-data.yml, "
        f"scripts/automated_send_reminder_email.py).</p>"
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
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; zoho-reminder-email-script/1.0)"})

    print("Requesting a Zoho access token ...", file=sys.stderr)
    try:
        access_token, _api_domain = get_access_token(session, client_id, client_secret, refresh_token)
    except requests.HTTPError as e:
        body = e.response.text if e.response is not None else "<no body>"
        print(f"Error: Zoho token request failed: {e}\nResponse body: {body}", file=sys.stderr)
        sys.exit(1)

    subject, content = build_email()
    print(f"Sending reminder email to {TO_ADDRESS}: {subject!r}", file=sys.stderr)
    try:
        send_email(session, access_token, subject, content)
    except requests.HTTPError as e:
        body = e.response.text if e.response is not None else "<no body>"
        print(f"Error: Zoho Mail send failed: {e}\nResponse body: {body}", file=sys.stderr)
        sys.exit(1)

    print(f"Reminder email sent to {TO_ADDRESS}.")


if __name__ == "__main__":
    main()
