"""Unit tests for swarmbee-bakery.

Network calls are mocked. One optional live test against bakery.swarmandbee.ai
gated behind SWARMBEE_LIVE=1.
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from swarmbee_bakery import client, order
from swarmbee_bakery.cli import build_parser, main


# ─── client ──────────────────────────────────────────────────────────────────

def test_base_url_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("BAKERY_BASE_URL", None)
        assert client.base_url() == "https://bakery.swarmandbee.ai"


def test_base_url_env_override():
    with patch.dict(os.environ, {"BAKERY_BASE_URL": "http://localhost:8090/"}):
        assert client.base_url() == "http://localhost:8090"


@patch("swarmbee_bakery.client.requests.get")
def test_fetch_menu_calls_correct_url(mock_get):
    mock_get.return_value = MagicMock(status_code=200,
                                       json=lambda: {"bakery": {"name": "Test"}})
    mock_get.return_value.raise_for_status = MagicMock()
    result = client.fetch_menu()
    assert result == {"bakery": {"name": "Test"}}
    args, kwargs = mock_get.call_args
    assert args[0].endswith("/menu.json")


@patch("swarmbee_bakery.client.requests.get")
def test_fetch_sample_uses_domain(mock_get):
    mock_get.return_value = MagicMock(status_code=200,
                                       json=lambda: {"pack": "finance", "pairs": []})
    mock_get.return_value.raise_for_status = MagicMock()
    client.fetch_sample("finance")
    args, kwargs = mock_get.call_args
    assert args[0].endswith("/samples/finance.json")


def test_menu_summary_extracts_in_stock_only():
    menu = {
        "bakery": {"name": "Bakery", "doctrine": "bake fresh"},
        "skus": {
            "by_the_pound": {
                "stock": [
                    {"name": "a", "status": "in_stock", "pairs": 100,
                     "domain": "finance", "freshness": {"last_rebake": "2026-05-01"},
                     "sample_endpoint": "/samples/finance.json"},
                    {"name": "b", "status": "raw_not_audited", "pairs": 50,
                     "domain": "aviation"},
                ]
            },
            "the_500_pack": {"starter_kits": [
                {"name": "kit1", "domain": "finance", "description": "x"}
            ]},
        },
        "ordering": {"intake_endpoint": "https://x/y"},
    }
    s = client.menu_summary(menu)
    assert len(s["in_stock_corpora"]) == 1
    assert s["in_stock_corpora"][0]["name"] == "a"
    assert len(s["starter_kits"]) == 1


def test_sha256_payload_is_deterministic():
    p = {"name": "Jane", "email": "jane@x.com", "z": 1, "a": 2}
    h1 = client.sha256_payload(p)
    h2 = client.sha256_payload({"a": 2, "z": 1, "email": "jane@x.com", "name": "Jane"})
    assert h1 == h2
    assert len(h1) == 64


# ─── order ────────────────────────────────────────────────────────────────────

def test_build_payload_minimal():
    p = order.build_payload(name="Jane", email="jane@x.com",
                             sku="500-pack", domain="finance",
                             failure_mode="fabrication detection")
    assert p["name"] == "Jane"
    assert p["email"] == "jane@x.com"
    assert p["work_type"] == "ai_eval"
    assert "fabrication detection" in p["description"]
    assert "500-pack" in p["description"]
    assert "finance" in p["description"]


def test_build_payload_invalid_sku():
    with pytest.raises(ValueError, match="invalid sku"):
        order.build_payload(name="x", email="x@x.x",
                             sku="bulk-discount-tier-7", domain="finance")


def test_build_payload_invalid_domain():
    with pytest.raises(ValueError, match="invalid domain"):
        order.build_payload(name="x", email="x@x.x",
                             sku="500-pack", domain="dishwashers")


def test_build_payload_optional_fields():
    p = order.build_payload(name="x", email="x@x.x", sku="by-the-pound",
                             domain="medical", company="Acme", budget="$2000",
                             deadline="2026-06-15", notes="urgent")
    assert p["company"] == "Acme"
    assert p["budget"] == "$2000"
    assert p["deadline"] == "2026-06-15"
    assert "urgent" in p["description"]


@patch("swarmbee_bakery.order.requests.post")
def test_submit_returns_status_and_body(mock_post):
    mock_post.return_value = MagicMock(status_code=200,
                                        json=lambda: {"ok": True, "channel": "discord"})
    status, body = order.submit({"x": 1})
    assert status == 200
    assert body == {"ok": True, "channel": "discord"}


@patch("swarmbee_bakery.order.requests.post")
def test_submit_network_error_is_handled(mock_post):
    import requests as _r
    mock_post.side_effect = _r.ConnectionError("dns")
    status, body = order.submit({"x": 1})
    assert status == 0
    assert body["ok"] is False
    assert body["error"] == "network_error"


@patch("swarmbee_bakery.order.requests.post")
def test_submit_with_fallback_uses_bounty_on_404(mock_post):
    responses = [
        MagicMock(status_code=404, json=lambda: {"error": "not_found"}),
        MagicMock(status_code=200, json=lambda: {"ok": True}),
    ]
    mock_post.side_effect = responses
    status, body, endpoint = order.submit_with_fallback({"x": 1})
    assert status == 200
    assert endpoint == "/api/bounty-intake"
    assert mock_post.call_count == 2


def test_receipt_includes_sha256_and_byte_count():
    payload = {"name": "x", "email": "x@x.x"}
    r = order.receipt(payload)
    assert "payload_sha256" in r
    assert len(r["payload_sha256"]) == 64
    assert r["payload_bytes"] > 0
    assert r["timestamp_utc"].endswith("Z")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def test_parser_requires_subcommand():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_version():
    parser = build_parser()
    args = parser.parse_args(["version"])
    assert args.cmd == "version"


def test_parser_order_requires_name_email_sku_domain():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["order"])


@patch("swarmbee_bakery.client.requests.get")
def test_cli_menu_json_output(mock_get, capsys):
    mock_get.return_value = MagicMock(status_code=200,
                                       json=lambda: {"bakery": {"name": "Test"}})
    mock_get.return_value.raise_for_status = MagicMock()
    rc = main(["menu", "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Test" in out
    parsed = json.loads(out)
    assert "bakery" in parsed


@patch("swarmbee_bakery.order.requests.post")
def test_cli_order_dry_run_does_not_post(mock_post, capsys):
    rc = main(["order", "--name", "Jane", "--email", "jane@x.com",
                "--sku", "500-pack", "--domain", "finance",
                "--failure-mode", "fabrication detection"])
    assert rc == 0
    assert mock_post.call_count == 0  # dry-run, no network
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "payload_sha256" in out


def test_cli_receipt_from_stdin(capsys, monkeypatch):
    import io
    payload = '{"x":1,"name":"Jane"}'
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    rc = main(["receipt"])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert len(parsed["payload_sha256"]) == 64


def test_cli_receipt_from_file(tmp_path, capsys):
    f = tmp_path / "p.json"
    f.write_text('{"a": 1}')
    rc = main(["receipt", "--file", str(f)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "payload_sha256" in out


# ─── optional live test ─────────────────────────────────────────────────────

@pytest.mark.skipif(os.environ.get("SWARMBEE_LIVE") != "1",
                     reason="live network test; set SWARMBEE_LIVE=1 to enable")
def test_live_fetch_menu_against_production():
    menu = client.fetch_menu()
    assert "bakery" in menu
    assert "skus" in menu
    assert "by_the_pound" in menu["skus"]
    assert "the_500_pack" in menu["skus"]


@pytest.mark.skipif(os.environ.get("SWARMBEE_LIVE") != "1",
                     reason="live network test; set SWARMBEE_LIVE=1 to enable")
def test_live_fetch_all_sample_packs():
    for d in ["finance", "medical", "healing", "agents", "legal"]:
        pack = client.fetch_sample(d)
        assert pack["pack"] == d
        assert len(pack.get("pairs", [])) >= 5
