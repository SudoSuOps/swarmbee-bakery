"""Order submission to the bakery intake endpoint.

DRY-RUN BY DEFAULT. The CLI must pass `--confirm` to actually POST. This
matches the BountySkill operator-boundary doctrine: no auto-submit, no
auto-spend, human decides.

When confirmed, posts to /api/bakery-intake (falls back to /api/bounty-intake
during transition). Returns the server response + local sha256 receipt of
the exact payload submitted.
"""
from __future__ import annotations

import time
from typing import Any

import requests

from .client import base_url, sha256_payload, USER_AGENT, DEFAULT_TIMEOUT


VALID_SKUS = {"500-pack", "by-the-pound"}
VALID_DOMAINS = {
    "finance", "medical", "healing", "agents", "legal",
    "GEO_audit", "geo_audit", "custom",
}


def build_payload(*,
                   name: str,
                   email: str,
                   sku: str,
                   domain: str,
                   failure_mode: str | None = None,
                   budget: str | None = None,
                   deadline: str | None = None,
                   company: str | None = None,
                   notes: str | None = None) -> dict[str, Any]:
    """Build the payload the bakery intake endpoint expects."""
    if sku not in VALID_SKUS:
        raise ValueError(f"invalid sku '{sku}'; must be one of {sorted(VALID_SKUS)}")
    if domain not in VALID_DOMAINS:
        raise ValueError(f"invalid domain '{domain}'; must be one of {sorted(VALID_DOMAINS)}")

    work_type_map = {
        "finance": "ai_eval",
        "medical": "dataset",
        "healing": "dataset",
        "agents": "ai_eval",
        "legal": "dataset",
        "GEO_audit": "geo_audit",
        "geo_audit": "geo_audit",
        "custom": "other",
    }

    description_parts = [
        f"SKU: {sku}",
        f"Domain: {domain}",
    ]
    if failure_mode:
        description_parts.append(f"Failure mode: {failure_mode}")
    if notes:
        description_parts.append(f"Notes: {notes}")
    description_parts.append(
        f"Submitted via swarmbee-bakery CLI v0.1.3 at "
        f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}"
    )
    description = "\n".join(description_parts)

    payload = {
        "name": name,
        "email": email,
        "work_type": work_type_map.get(domain, "other"),
        "description": description,
    }
    if company:
        payload["company"] = company
    if budget:
        payload["budget"] = budget
    if deadline:
        payload["deadline"] = deadline

    return payload


def submit(payload: dict[str, Any], *,
            endpoint_path: str = "/api/bakery-intake",
            timeout: int = DEFAULT_TIMEOUT) -> tuple[int, dict[str, Any]]:
    """POST the payload to the bakery intake endpoint.

    Returns (status_code, response_body_or_diagnostic_dict).
    Never raises on HTTP-level failure — the caller handles non-200 responses.
    """
    url = f"{base_url()}{endpoint_path}"
    try:
        r = requests.post(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as e:
        return 0, {"ok": False, "error": "network_error", "detail": str(e)}

    try:
        body = r.json()
    except Exception:
        body = {"ok": False, "error": "non_json_response", "body_preview": r.text[:500]}
    return r.status_code, body


def submit_with_fallback(payload: dict[str, Any]) -> tuple[int, dict[str, Any], str]:
    """Try /api/bakery-intake; if 404 fall back to /api/bounty-intake.

    Returns (status_code, body, endpoint_used).
    """
    status, body = submit(payload, endpoint_path="/api/bakery-intake")
    if status == 404:
        status, body = submit(payload, endpoint_path="/api/bounty-intake")
        return status, body, "/api/bounty-intake"
    return status, body, "/api/bakery-intake"


def receipt(payload: dict[str, Any]) -> dict[str, Any]:
    """Local receipt for what we submitted (or would submit)."""
    return {
        "payload_sha256": sha256_payload(payload),
        "payload_bytes": len(
            __import__("json").dumps(payload, sort_keys=True, separators=(",", ":"))
        ),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
