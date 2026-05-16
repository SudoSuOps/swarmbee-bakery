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


def cmd_order(args: argparse.Namespace) -> int:
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
    print(f"  response    : {json.dumps(body, indent=2)}")

    if 200 <= status < 300 and body.get("ok"):
        print("\n  ORDER SUBMITTED. A human reads every submission. Reply within one business day.")
        return 0
    _err(f"submission rejected (status {status}). Check response above.")
    return 1


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

    # Single-pack fetch
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
    po.add_argument("--sku", required=True, choices=["500-pack", "by-the-pound"])
    po.add_argument("--domain", required=True,
                     choices=["finance", "medical", "healing", "agents", "legal",
                              "GEO_audit", "geo_audit", "custom"])
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
