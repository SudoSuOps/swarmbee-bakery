"""HTTP client for the Swarm & Bee bakery JSON endpoints.

Stateless. Reads BAKERY_BASE_URL from env (default: https://bakery.swarmandbee.ai).
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import requests


DEFAULT_BASE_URL = "https://bakery.swarmandbee.ai"
USER_AGENT = "swarmbee-bakery-cli/0.1.5"
DEFAULT_TIMEOUT = 10


def base_url() -> str:
    return os.environ.get("BAKERY_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _get(path: str) -> dict[str, Any]:
    url = f"{base_url()}{path}"
    r = requests.get(url,
                     headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                     timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    return r.json()


def fetch_menu() -> dict[str, Any]:
    """Returns the full bakery menu manifest."""
    return _get("/menu.json")


def fetch_sample_index() -> dict[str, Any]:
    """Returns the sample-pack index."""
    return _get("/samples/index.json")


def fetch_sample(domain: str) -> dict[str, Any]:
    """Returns a sample pack for one domain (finance|medical|healing|agents|legal)."""
    return _get(f"/samples/{domain}.json")


def fetch_free_index() -> dict[str, Any]:
    """Returns the free-pack index — 10 medical sample packs, 50 cells each."""
    return _get("/samples/free/index.json")


def _post(path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """POST helper. Returns (status, body). Never raises on HTTP error."""
    url = f"{base_url()}{path}"
    try:
        r = requests.post(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as e:
        return 0, {"ok": False, "error": "network_error", "detail": str(e)}
    try:
        body = r.json()
    except Exception:
        body = {"ok": False, "error": "non_json_response", "body_preview": r.text[:500]}
    return r.status_code, body


def lookup_order(order_id: str, email: str) -> tuple[int, dict[str, Any]]:
    """POST /api/account-lookup → order details + event history."""
    return _post("/api/account-lookup", {"order_id": order_id, "email": email})


def fetch_cookbook_index() -> dict[str, Any]:
    """Returns the cookbooks index — pre-curated recipe bundles."""
    return _get("/cookbooks/index.json")


def fetch_cookbook_markdown(slug: str) -> str:
    """Returns the raw markdown content of a single cookbook."""
    url = f"{base_url()}/cookbooks/{slug}.md"
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    return r.text


def list_orders(email: str) -> tuple[int, dict[str, Any]]:
    """POST /api/orders-list → brief list of orders for this email."""
    return _post("/api/orders-list", {"email": email})


def fetch_free_pack(slug: str) -> list[dict[str, Any]]:
    """Returns one free pack as a list of cells (JSONL parsed line-by-line)."""
    url = f"{base_url()}/samples/free/{slug}.jsonl"
    r = requests.get(url,
                     headers={"User-Agent": USER_AGENT, "Accept": "application/x-jsonl, text/plain"},
                     timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    cells: list[dict[str, Any]] = []
    for line in r.text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            cells.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return cells


def menu_summary(menu: dict[str, Any]) -> dict[str, Any]:
    """Compact summary of the menu — for terminal display."""
    sk = menu.get("skus", {})
    stock = sk.get("by_the_pound", {}).get("stock", [])
    in_stock = [s for s in stock if s.get("status") == "in_stock"]
    starter_kits = sk.get("the_500_pack", {}).get("starter_kits", [])
    return {
        "bakery": menu.get("bakery", {}).get("name", ""),
        "doctrine": menu.get("bakery", {}).get("doctrine", ""),
        "in_stock_corpora": [
            {
                "name": s.get("name"),
                "domain": s.get("domain"),
                "pairs": s.get("pairs"),
                "last_rebake": s.get("freshness", {}).get("last_rebake"),
                "sample": s.get("sample_endpoint"),
            }
            for s in in_stock
        ],
        "starter_kits": [
            {
                "name": k.get("name"),
                "domain": k.get("domain"),
                "description": k.get("description"),
            }
            for k in starter_kits
        ],
        "ordering_intake": menu.get("ordering", {}).get("intake_endpoint"),
    }


def sha256_payload(payload: dict[str, Any]) -> str:
    """Deterministic sha256 of a JSON payload (sorted keys, compact separators)."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
