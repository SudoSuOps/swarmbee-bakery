"""swarmbee-bakery · CLI entry point.

Subcommands:
    menu              fetch and pretty-print /menu.json
    sample <domain>   fetch a sample pack (finance|medical|healing|agents|legal)
    order             dry-run an order; pass --confirm to actually submit
    receipt           hash a JSON payload from stdin (audit utility)
    version           print version + endpoint
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, client, order


# ─── output helpers ─────────────────────────────────────────────────────────

def _print_table(rows: list[dict], cols: list[tuple[str, str, int]]) -> None:
    """Print a simple aligned table. cols = [(header, key, width), ...]."""
    header = "  ".join(h.ljust(w) for h, _, w in cols)
    print(header)
    print("  ".join("-" * w for _, _, w in cols))
    for r in rows:
        line = "  ".join(str(r.get(k, "")).ljust(w)[:w] for _, k, w in cols)
        print(line)


def _err(msg: str) -> None:
    print(f"swarmbee-bakery: {msg}", file=sys.stderr)


# ─── subcommands ────────────────────────────────────────────────────────────

def cmd_menu(args: argparse.Namespace) -> int:
    try:
        menu = client.fetch_menu()
    except Exception as e:
        _err(f"could not fetch menu: {e}")
        return 2

    if args.json:
        print(json.dumps(menu, indent=2))
        return 0

    bakery = menu.get("bakery", {})
    print(f"\n  {bakery.get('name', '')}")
    print(f"  {bakery.get('url', '')}")
    print(f"  {bakery.get('doctrine', '')}\n")

    print("  ─── IN STOCK (by the pound) ────────────────────────────────────")
    stock = menu.get("skus", {}).get("by_the_pound", {}).get("stock", [])
    in_stock = [s for s in stock if s.get("status") == "in_stock"]
    if args.domain:
        in_stock = [s for s in in_stock if args.domain in (s.get("domain") or "")]
    rows = []
    for s in in_stock:
        rows.append({
            "name": s.get("name", ""),
            "tier": s.get("tier_grade", ""),
            "domain": s.get("domain", ""),
            "pairs": f"{s.get('pairs', 0):,}",
            "seal": "sealed" if s.get("tribunal_sealed") else "pre",
            "rebake": s.get("freshness", {}).get("last_rebake", ""),
        })
    if rows:
        _print_table(rows, [
            ("NAME", "name", 26),
            ("TIER", "tier", 6),
            ("DOMAIN", "domain", 22),
            ("PAIRS", "pairs", 10),
            ("TRIBUNAL", "seal", 8),
            ("LAST RE-BAKE", "rebake", 12),
        ])
    else:
        print("  (no corpora match filter)")

    print("\n  ─── 500-PACK STARTER KITS ──────────────────────────────────────")
    kits = menu.get("skus", {}).get("the_500_pack", {}).get("starter_kits", [])
    if args.domain:
        kits = [k for k in kits if args.domain in (k.get("domain") or "") or k.get("domain") == "any"]
    for k in kits:
        print(f"  · {k.get('name'):30s} · domain={k.get('domain')}")
        desc = k.get("description", "")
        print(f"      {desc}")

    print("\n  ─── SAMPLE PACKS ───────────────────────────────────────────────")
    packs = menu.get("sample_packs", {}).get("packs", {})
    base = client.base_url()
    for p, url in packs.items():
        print(f"  · {p:10s}  →  {base}{url}")

    ordering = menu.get("ordering", {})
    print("\n  ─── HOW TO ORDER ───────────────────────────────────────────────")
    doctrine = ordering.get("channel_doctrine")
    if doctrine:
        print(f"  {doctrine}")
    install = ordering.get("cli_install")
    browse = ordering.get("cli_browse")
    example = ordering.get("cli_order_example")
    if install:
        print(f"\n  install : {install}")
    if browse:
        print(f"  browse  : {browse}")
    if example:
        print(f"  order   : {example}")
    intake = ordering.get("intake_endpoint")
    if intake:
        print(f"\n  intake endpoint : {intake}")
    rails = ordering.get("settlement_rails")
    if isinstance(rails, dict) and rails:
        print("  settlement      :")
        for k, v in rails.items():
            print(f"      · {k}: {v}")
    print()
    return 0


def cmd_sample(args: argparse.Namespace) -> int:
    try:
        pack = client.fetch_sample(args.domain)
    except Exception as e:
        _err(f"could not fetch sample pack '{args.domain}': {e}")
        return 2

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(pack, indent=2))
        print(f"wrote sample pack '{args.domain}' to {out_path} "
              f"({len(out_path.read_text())} bytes)")
        return 0

    if args.summary:
        pairs = pack.get("pairs", [])
        print(f"\n  ─── {args.domain.upper()} SAMPLE PACK ({len(pairs)} pairs) ───────")
        print(f"  {pack.get('sample_disclaimer', '')}\n")
        for p in pairs:
            grade = p.get("tier_grade", "?")
            rubric = p.get("rubric", {})
            avg = (sum(rubric.values()) / len(rubric)) if rubric else 0
            note = p.get("metadata", {}).get("note", "")
            print(f"  · {p.get('id'):24s} [{grade:8s}] avg_rubric={avg:.1f}")
            instruction = p.get("instruction", "")
            if instruction:
                print(f"      {instruction[:80]}")
            if note:
                print(f"      note: {note[:140]}")
        print()
        return 0

    # Default: full JSON to stdout
    print(json.dumps(pack, indent=2))
    return 0


_EMAIL_RX = __import__("re").compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def cmd_order(args: argparse.Namespace) -> int:
    # Validate email before doing anything else — fail-fast, no payload print on bad input
    if not _EMAIL_RX.match(args.email or ""):
        _err(f"invalid email address: {args.email!r}")
        return 2
    try:
        payload = order.build_payload(
            name=args.name,
            email=args.email,
            sku=args.sku,
            domain=args.domain,
            failure_mode=args.failure_mode,
            budget=args.budget,
            deadline=args.deadline,
            company=args.company,
            notes=args.notes,
            cookbook=getattr(args, "cookbook", None),
            settlement_rail=getattr(args, "settlement", None),
        )
    except ValueError as e:
        _err(str(e))
        return 2

    receipt = order.receipt(payload)

    print("\n  ─── ORDER PAYLOAD ──────────────────────────────────────────────")
    print(json.dumps(payload, indent=2))
    print("\n  ─── LOCAL RECEIPT ──────────────────────────────────────────────")
    print(f"  payload_sha256 : {receipt['payload_sha256']}")
    print(f"  payload_bytes  : {receipt['payload_bytes']}")
    print(f"  timestamp_utc  : {receipt['timestamp_utc']}")

    if not args.confirm:
        print("\n  DRY RUN — nothing submitted. Re-run with --confirm to actually post.")
        return 0

    print("\n  ─── SUBMITTING ─────────────────────────────────────────────────")
    status, body, endpoint = order.submit_with_fallback(payload)
    print(f"  endpoint    : {client.base_url()}{endpoint}")
    print(f"  http_status : {status}")

    if 200 <= status < 300 and body.get("ok"):
        oid = body.get("order_id")
        if oid:
            # New D1-backed response shape — pretty print
            print(f"\n  ─── ORDER PERSISTED ────────────────────────────────────────────")
            print(f"  order_id          : {oid}")
            print(f"  status            : {body.get('status', 'pending')}")
            print(f"  payload_sha256    : {body.get('payload_sha256', '—')}")
            email_st = body.get("receipt_email", {})
            if isinstance(email_st, dict):
                if email_st.get("sent"):
                    print(f"  email receipt     : ✓ sent to {args.email}")
                else:
                    print(f"  email receipt     : ✗ failed ({email_st.get('error', 'unknown')})")
            next_step = body.get("next_step")
            if next_step:
                print(f"\n  {next_step}")
            check = body.get("check_status")
            if check:
                print(f"\n  check status anytime:")
                print(f"    {check}")
            print()
        else:
            # Legacy response (no D1 yet) — just confirm
            print("\n  ORDER SUBMITTED. A human reads every submission. Reply within one business day.")
            print(f"  response: {json.dumps(body, indent=2)}")
        return 0
    print(f"  response    : {json.dumps(body, indent=2)}")
    _err(f"submission rejected (status {status}). Check response above.")
    return 1


def cmd_cookbook(args: argparse.Namespace) -> int:
    """List all cookbooks or show one cookbook's full recipe."""
    try:
        idx = client.fetch_cookbook_index()
    except Exception as e:
        _err(f"could not fetch cookbook index: {e}")
        return 2

    cookbooks = idx.get("cookbooks", [])

    # specific cookbook → render its markdown
    if args.slug:
        slug = args.slug
        match = next((c for c in cookbooks if c.get("slug") == slug), None)
        if not match:
            _err(f"unknown cookbook '{slug}'. Available: {', '.join(c.get('slug','') for c in cookbooks)}")
            return 2
        if args.json:
            print(json.dumps(match, indent=2))
            return 0
        try:
            md = client.fetch_cookbook_markdown(slug)
        except Exception as e:
            _err(f"could not fetch markdown: {e}")
            return 2
        print(md)
        print()
        return 0

    # list all
    if args.json:
        print(json.dumps(idx, indent=2))
        return 0

    print(f"\n  {idx.get('title', 'Swarm & Bee Cookbooks')}")
    print(f"  {idx.get('doctrine', '')}\n")
    hr = idx.get("headline_receipt", {})
    if hr:
        print(f"  HEADLINE RECEIPT: {hr.get('claim','')}")
        print(f"  ↳ implication: {hr.get('implication','')}\n")

    print("  ─── COOKBOOKS ──────────────────────────────────────────────────")
    rows = [{
        "name": c.get("name",""),
        "slug": c.get("slug",""),
        "cells": str(c.get("cells",0)),
        "price": f"${c.get('price_usd',0)}",
        "tier": c.get("tier",""),
    } for c in cookbooks]
    _print_table(rows, [
        ("NAME", "name", 30),
        ("SLUG", "slug", 30),
        ("CELLS", "cells", 7),
        ("PRICE", "price", 8),
        ("TIER", "tier", 16),
    ])
    print(f"\n  shared recipe : {idx.get('shared_recipe',{}).get('label','—')}")
    print(f"  shared eval   : {idx.get('shared_eval',{}).get('name','—')} ({idx.get('shared_eval',{}).get('n_probes',0)} probes)")
    in_dev = idx.get("cookbooks_in_development") or idx.get("in_development") or []
    if in_dev:
        print(f"  in development: {len(in_dev)} more cookbooks scoped\n")
    else:
        print()
    print("  detail   : swarmbee-bakery cookbook <slug>")
    print("  order    : swarmbee-bakery order --sku cookbook --cookbook <slug> ...\n")
    return 0


def cmd_account(args: argparse.Namespace) -> int:
    """Look up one order by (order_id, email) — durable D1 lookup, no auth."""
    status, body = client.lookup_order(args.order, args.email)
    if args.json:
        print(json.dumps(body, indent=2))
        return 0 if (200 <= status < 300) else 1
    if status == 404:
        _err("order not found (or email does not match)")
        return 1
    if not (200 <= status < 300) or not body.get("ok"):
        _err(f"lookup failed (status {status}): {body.get('error', 'unknown')}")
        return 1

    o = body.get("order", {})
    events = body.get("events", [])

    def fld(label: str, value):
        if value not in (None, "", 0):
            print(f"  {label:24s} {value}")

    print(f"\n  ─── ORDER {o.get('order_id', '?')} ─────────────────────────────────")
    fld("status", o.get("status"))
    fld("status_updated_at", o.get("status_updated_at"))
    fld("created_at", o.get("created_at"))
    print()
    fld("channel", o.get("channel"))
    fld("sku", o.get("sku"))
    fld("sku_id", o.get("sku_id"))
    fld("domain", o.get("domain"))
    fld("pairs_requested", o.get("pairs_requested"))
    fld("failure_mode", o.get("failure_mode"))
    fld("settlement_rail", o.get("settlement_rail"))
    fld("name", o.get("name"))
    fld("company", o.get("company"))
    fld("notes", o.get("notes"))
    print()
    print("  ─── PAYMENT ──────────────────────────────────────────────────")
    fld("invoice_url", o.get("invoice_url"))
    fld("invoice_amount_usd", o.get("invoice_amount_usd"))
    fld("paid_at", o.get("paid_at"))
    print()
    print("  ─── FULFILLMENT ──────────────────────────────────────────────")
    fld("assembled_at", o.get("assembled_at"))
    fld("shipped_at", o.get("shipped_at"))
    fld("bundle_sha256", o.get("bundle_sha256"))
    fld("download_url", o.get("download_url"))
    fld("download_expires_at", o.get("download_expires_at"))
    fld("hedera_anchor_tx", o.get("hedera_anchor_tx"))
    print()
    print("  ─── PROVENANCE ───────────────────────────────────────────────")
    fld("payload_sha256", o.get("payload_sha256"))
    print()
    if events:
        print(f"  ─── EVENT LOG ({len(events)}) ─────────────────────────────────────")
        for e in events:
            ts = e.get("created_at", "")[:19]
            etype = e.get("event_type", "")
            actor = e.get("actor", "")
            transition = ""
            if e.get("to_status"):
                transition = f" {e.get('from_status') or '∅'} → {e.get('to_status')}"
            detail = e.get("detail") or ""
            print(f"  · {ts}  [{etype:14s}] actor={actor:12s}{transition}")
            if detail:
                print(f"      {detail[:120]}")
        print()
    return 0


def cmd_orders(args: argparse.Namespace) -> int:
    """List all orders for an email — brief shape.
    Requires a known order_id as proof to prevent email enumeration."""
    status, body = client.list_orders(args.email, args.proof_order)
    if args.json:
        print(json.dumps(body, indent=2))
        return 0 if (200 <= status < 300) else 1
    if not (200 <= status < 300) or not body.get("ok"):
        _err(f"list failed (status {status}): {body.get('error', 'unknown')}")
        return 1

    orders = body.get("orders", [])
    print(f"\n  ─── ORDERS FOR {body.get('email', args.email)} ({len(orders)}) ───────")
    if not orders:
        print("  (no orders found)")
        print()
        return 0
    rows = [{
        "order_id": o.get("order_id", ""),
        "created": (o.get("created_at") or "")[:10],
        "status": o.get("status", ""),
        "channel": o.get("channel", ""),
        "sku": o.get("sku") or "—",
        "domain": o.get("domain") or "—",
        "rail": o.get("settlement_rail") or "—",
    } for o in orders]
    _print_table(rows, [
        ("ORDER ID", "order_id", 22),
        ("CREATED", "created", 11),
        ("STATUS", "status", 12),
        ("CHANNEL", "channel", 10),
        ("SKU", "sku", 14),
        ("DOMAIN", "domain", 22),
        ("RAIL", "rail", 10),
    ])
    print(f"\n  detail: swarmbee-bakery account --order <ID> --email {body.get('email', args.email)}\n")
    return 0


def cmd_free(args: argparse.Namespace) -> int:
    """Browse, download, or bulk-fetch the 10 free medical sample packs."""
    try:
        index = client.fetch_free_index()
    except Exception as e:
        _err(f"could not fetch free-pack index: {e}")
        return 2

    packs = index.get("packs", [])

    # --all : bulk download every pack
    if args.all:
        out_dir = Path(args.out_dir) if args.out_dir else Path("./swarm-samples")
        out_dir.mkdir(parents=True, exist_ok=True)
        total_cells = 0
        for p in packs:
            slug = p.get("slug")
            if not slug:
                continue
            try:
                cells = client.fetch_free_pack(slug)
            except Exception as e:
                _err(f"failed to fetch {slug}: {e}")
                continue
            out_path = out_dir / f"{slug}.jsonl"
            with open(out_path, "w") as f_out:
                for c in cells:
                    f_out.write(json.dumps(c, ensure_ascii=False) + "\n")
            print(f"  ✓ {p.get('flavor'):30s}  {len(cells):>4} cells  →  {out_path}")
            total_cells += len(cells)
        manifest_path = out_dir / "index.json"
        manifest_path.write_text(json.dumps(index, indent=2))
        print(f"\n  index → {manifest_path}")
        print(f"  total free cells: {total_cells}")
        return 0

    # No pack arg : list available
    if not args.pack:
        print(f"\n  {index.get('title', '10 free medical sample packs')}")
        print(f"  {index.get('doctrine', '')}\n")
        print("  ─── FREE PACKS ─────────────────────────────────────────────────")
        rows = [{
            "flavor": p.get("flavor", ""),
            "tier": p.get("tier_grade", ""),
            "slug": p.get("slug", ""),
            "pairs": str(p.get("pairs", 0)),
        } for p in packs]
        _print_table(rows, [
            ("FLAVOR", "flavor", 26),
            ("TIER", "tier", 6),
            ("SLUG", "slug", 22),
            ("CELLS", "pairs", 8),
        ])
        print(f"\n  total: {index.get('total_free_cells', 0)} cells across {len(packs)} packs · {index.get('sample_size_per_pack', 50)} cells each\n")
        print(f"  one pack    : swarmbee-bakery free <slug>")
        print(f"  one pack -> : swarmbee-bakery free <slug> --out path.jsonl")
        print(f"  all packs   : swarmbee-bakery free --all --out-dir ./samples/\n")
        return 0

    # Single-pack fetch — validate slug against index first to avoid silently
    # parsing an HTML 404 fallback as garbage JSONL
    valid_slugs = {p.get("slug") for p in packs if p.get("slug")}
    if args.pack not in valid_slugs:
        _err(f"unknown free pack '{args.pack}'. Available: {', '.join(sorted(s for s in valid_slugs if s))}")
        return 2
    try:
        cells = client.fetch_free_pack(args.pack)
    except Exception as e:
        _err(f"could not fetch free pack '{args.pack}': {e}")
        return 2

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f_out:
            for c in cells:
                f_out.write(json.dumps(c, ensure_ascii=False) + "\n")
        print(f"wrote {len(cells)} cells to {out_path}")
        return 0

    if args.summary:
        pack_meta = next((p for p in packs if p.get("slug") == args.pack), {})
        print(f"\n  ─── {pack_meta.get('flavor', args.pack).upper()} ({len(cells)} cells) ───────")
        print(f"  {pack_meta.get('note', '')}\n")
        for c in cells[:10]:
            q = (c.get("question") or "")[:90]
            tier = c.get("tier", "—")
            spec = c.get("specialty", "—")
            print(f"  · [{tier:14s}] {spec:22s} {q}")
        if len(cells) > 10:
            print(f"  · ... and {len(cells) - 10} more")
        print()
        return 0

    # Default: jsonl to stdout
    for c in cells:
        print(json.dumps(c, ensure_ascii=False))
    return 0


def cmd_receipt(args: argparse.Namespace) -> int:
    """Hash a JSON payload from stdin or file. Audit utility."""
    if args.file:
        data = Path(args.file).read_text()
    else:
        data = sys.stdin.read()
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as e:
        _err(f"invalid JSON: {e}")
        return 2
    r = order.receipt(payload)
    print(json.dumps(r, indent=2))
    return 0


def cmd_version(_: argparse.Namespace) -> int:
    print(f"swarmbee-bakery {__version__}")
    print(f"endpoint: {client.base_url()}")
    return 0


# ─── argparse wire-up ───────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="swarmbee-bakery",
        description="CLI for the Swarm & Bee dataset bakery. "
                    "Browse the menu, taste the samples, order curated AI training corpora.",
        epilog="Override base URL via env: BAKERY_BASE_URL=https://...",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pm = sub.add_parser("menu", help="fetch and pretty-print the bakery menu")
    pm.add_argument("--json", action="store_true", help="print raw JSON")
    pm.add_argument("--domain", help="filter to one domain (finance|medical|...)")
    pm.set_defaults(fn=cmd_menu)

    ps = sub.add_parser("sample", help="fetch a sample pack")
    ps.add_argument("domain", choices=["finance", "medical", "healing", "agents", "legal"])
    ps.add_argument("--out", help="save to file instead of stdout")
    ps.add_argument("--summary", action="store_true",
                     help="print a compact pair-by-pair summary (default: full JSON to stdout)")
    ps.set_defaults(fn=cmd_sample)

    po = sub.add_parser("order", help="build and (with --confirm) submit an order")
    po.add_argument("--name", required=True)
    po.add_argument("--email", required=True)
    po.add_argument("--sku", required=True, choices=["500-pack", "by-the-pound", "cookbook"])
    po.add_argument("--domain", required=True,
                     choices=["finance", "medical", "healing", "agents", "legal",
                              "GEO_audit", "geo_audit", "custom"])
    po.add_argument("--cookbook", help="cookbook slug — required when --sku cookbook (run `cookbook` to list)")
    po.add_argument("--settlement", choices=["stripe", "swarmusdc", "either"], default="either",
                     help="preferred settlement rail (default: either — human follows up with both options)")
    po.add_argument("--failure-mode", help="for 500-pack: the specific failure mode to repair")
    po.add_argument("--budget", help='e.g. "$2000 fixed" or "open"')
    po.add_argument("--deadline", help='e.g. "2026-06-15" or "no rush"')
    po.add_argument("--company", help="optional company name")
    po.add_argument("--notes", help="optional additional context")
    po.add_argument("--confirm", action="store_true",
                     help="actually POST. Without this flag, dry-run only.")
    po.set_defaults(fn=cmd_order)

    pf = sub.add_parser("free", help="browse and download the 10 free medical sample packs")
    pf.add_argument("pack", nargs="?", help="pack slug (e.g. dmack-royal-jelly); omit to list all")
    pf.add_argument("--all", action="store_true", help="download every free pack")
    pf.add_argument("--out", help="save single pack to this jsonl file (with pack arg)")
    pf.add_argument("--out-dir", help="save all packs to this directory (with --all)")
    pf.add_argument("--summary", action="store_true", help="print a compact summary of the pack")
    pf.set_defaults(fn=cmd_free)

    pc = sub.add_parser("cookbook", help="browse curated recipe bundles (1500/3000 cells, named ingredients)")
    pc.add_argument("slug", nargs="?", help="cookbook slug (e.g. glycemic-reasoning); omit to list all")
    pc.add_argument("--json", action="store_true", help="print raw JSON")
    pc.set_defaults(fn=cmd_cookbook)

    pa = sub.add_parser("account", help="look up one order by (order_id, email)")
    pa.add_argument("--order", required=True, help="order id, e.g. BAK-20260516-ABCD")
    pa.add_argument("--email", required=True, help="email used at order time")
    pa.add_argument("--json", action="store_true", help="print raw JSON response")
    pa.set_defaults(fn=cmd_account)

    plo = sub.add_parser("orders", help="list all orders for an email (requires proof_order_id)")
    plo.add_argument("--email", required=True, help="customer email")
    plo.add_argument("--proof-order", required=True,
                     help="any past order_id for this email (anti-enumeration; e.g. BAK-20260517-AQA7)")
    plo.add_argument("--json", action="store_true", help="print raw JSON response")
    plo.set_defaults(fn=cmd_orders)

    pr = sub.add_parser("receipt", help="compute sha256 receipt of a JSON payload")
    pr.add_argument("--file", help="read from file (default: stdin)")
    pr.set_defaults(fn=cmd_receipt)

    pv = sub.add_parser("version", help="print version + endpoint")
    pv.set_defaults(fn=cmd_version)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
