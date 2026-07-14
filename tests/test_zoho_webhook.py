"""Tests for scripts/sync_zoho_abn_webhook.py — the full-snapshot ABN sync.
See CLAUDE.md's two Zoho gotchas this directly guards against: ABNs arriving
in human display format ("44 645 215 194") must be normalized to bare digits
before being written, and a payload with zero usable ABNs must be refused
rather than silently overwriting the CSV with nothing (a single bad/truncated
delivery would otherwise wipe every member).
"""
import json

import pandas as pd
import pytest

import sync_zoho_abn_webhook as webhook


# ---------------------------------------------------------------------------
# normalize_abn
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("44 645 215 194", "44645215194"),
    ("44-645-215-194", "44645215194"),
    ("44645215194", "44645215194"),
    ("", ""),
    (None, ""),
    (149633116, "149633116"),  # a real 9-digit malformed ABN, per CLAUDE.md
])
def test_normalize_abn(raw, expected):
    assert webhook.normalize_abn(raw) == expected


# ---------------------------------------------------------------------------
# extract_abns
# ---------------------------------------------------------------------------

def test_extract_abns_keeps_valid_11_digit_abns_and_normalizes_spaces():
    accounts = [
        {"company_name": "Acme", "abn": "44 645 215 194"},
        {"company_name": "Beta", "abn": "12 345 678 901"},
    ]
    valid, skipped = webhook.extract_abns(accounts)
    assert valid == ["44645215194", "12345678901"]
    assert skipped == []


def test_extract_abns_skips_blank_and_wrong_length_abns_with_description():
    accounts = [
        {"company_name": "Deloitte", "abn": "149633116"},  # 9 digits, real case
        {"company_name": "NoAbnCo", "abn": ""},
        {"company_name": "GoodCo", "abn": "44 645 215 194"},
    ]
    valid, skipped = webhook.extract_abns(accounts)
    assert valid == ["44645215194"]
    assert len(skipped) == 2
    assert "Deloitte" in skipped[0]
    assert "NoAbnCo" in skipped[1]


def test_extract_abns_falls_back_to_account_id_then_unnamed_for_skip_description():
    accounts = [
        {"account_id": "acct-123", "abn": ""},
        {"abn": ""},
    ]
    _, skipped = webhook.extract_abns(accounts)
    assert "acct-123" in skipped[0]
    assert "<unnamed>" in skipped[1]


# ---------------------------------------------------------------------------
# main() — full script behavior, via env var + monkeypatched output path
# ---------------------------------------------------------------------------

@pytest.fixture
def abns_csv(tmp_path, monkeypatch):
    path = tmp_path / "Tech_Council_ABNs.csv"
    monkeypatch.setattr(webhook, "ABNS_CSV", path)
    return path


def _set_payload(monkeypatch, payload):
    monkeypatch.setenv("ZOHO_WEBHOOK_PAYLOAD", json.dumps(payload) if not isinstance(payload, str) else payload)


def test_main_writes_sorted_deduped_csv_on_valid_payload(monkeypatch, abns_csv):
    payload = {
        "sync_date": "14-Jul-2026",
        "account_count": 3,
        "accounts_data": [
            {"company_name": "Beta", "abn": "12 345 678 901"},
            {"company_name": "Acme", "abn": "44 645 215 194"},
            {"company_name": "Acme Duplicate", "abn": "44 645 215 194"},
        ],
    }
    _set_payload(monkeypatch, payload)
    webhook.main()

    written = pd.read_csv(abns_csv, dtype=str)
    assert written["ABN"].tolist() == ["12345678901", "44645215194"]


def test_main_exits_nonzero_when_payload_env_var_missing(monkeypatch, abns_csv):
    monkeypatch.delenv("ZOHO_WEBHOOK_PAYLOAD", raising=False)
    with pytest.raises(SystemExit) as exc:
        webhook.main()
    assert exc.value.code == 1


def test_main_exits_nonzero_on_invalid_json(monkeypatch, abns_csv):
    _set_payload(monkeypatch, "{not valid json")
    with pytest.raises(SystemExit) as exc:
        webhook.main()
    assert exc.value.code == 1


def test_main_exits_nonzero_when_accounts_data_missing_or_empty(monkeypatch, abns_csv):
    _set_payload(monkeypatch, {"accounts_data": []})
    with pytest.raises(SystemExit) as exc:
        webhook.main()
    assert exc.value.code == 1


def test_main_refuses_to_write_when_every_abn_is_invalid(monkeypatch, abns_csv):
    # This is the "don't silently wipe every member" guarantee — a payload
    # that parses fine but yields zero usable ABNs must not overwrite the CSV.
    payload = {"accounts_data": [{"company_name": "BadCo", "abn": ""}]}
    _set_payload(monkeypatch, payload)
    with pytest.raises(SystemExit) as exc:
        webhook.main()
    assert exc.value.code == 1
    assert not abns_csv.exists()


def test_main_warns_but_proceeds_on_account_count_mismatch(monkeypatch, abns_csv, capsys):
    payload = {
        "account_count": 5,  # doesn't match actual accounts_data length below
        "accounts_data": [{"company_name": "Acme", "abn": "44 645 215 194"}],
    }
    _set_payload(monkeypatch, payload)
    webhook.main()

    assert abns_csv.exists()
    stderr = capsys.readouterr().err
    assert "doesn't match" in stderr
