# swarmbee-bakery

CLI for the [Swarm & Bee dataset bakery](https://bakery.swarmandbee.ai). Order
curated AI training corpora from the terminal.

> **AI is a bakery first.** Signal is supply. Curators are bakers. Distribution
> is delivery. Fresh every day, with a shelf life. 500 fantastic muffins crush
> 25,000 ingredients. *Less is better.*

> **Compassionate intelligence** — organic datasets with real-world purpose.
> Medical / autoimmune is the lead vertical. The diabetes corpus is the seed.

## What you can do

```bash
swarmbee-bakery menu                     # browse the inventory
swarmbee-bakery menu --domain finance    # filter by domain
swarmbee-bakery sample finance --summary # taste the finance pack
swarmbee-bakery order --sku 500-pack \
  --domain finance \
  --failure-mode "math verification at honey confidence" \
  --name "Your Name" --email "you@you.dev"
# ⤷ prints the order payload + sha256 receipt, DRY RUN by default
swarmbee-bakery order ... --confirm      # add --confirm to actually submit
```

Every order is **dry-run by default**. A human reads every submission. The
CLI never auto-spends, never auto-submits without `--confirm`.

## Install

```bash
pip install swarmbee-bakery
```

Requires Python 3.10+. One runtime dep (`requests`).

## Subcommands

| command | purpose |
|---|---|
| `menu` | fetch + pretty-print the live `menu.json` from `bakery.swarmandbee.ai/menu.json` |
| `menu --json` | raw machine-readable JSON |
| `menu --domain <name>` | filter to one vertical (finance / medical / healing / agents / legal) |
| `sample <domain>` | fetch a sample pack (full JSON to stdout) |
| `sample <domain> --summary` | compact pair-by-pair summary |
| `sample <domain> --out path.json` | save to file |
| `order` | build (and with `--confirm`, submit) an order. Always prints a local sha256 receipt of the exact payload. |
| `receipt` | hash a JSON payload from stdin/file — audit utility |
| `version` | print version + endpoint |

## The two SKUs

### By the pound · wholesale corpora

For shops with a base model and a need for breadth. Bulk training corpora,
graded, deduped, freshness-stamped. Sold per 1,000 pairs.

```bash
swarmbee-bakery order --sku by-the-pound \
  --domain finance \
  --budget "100k pairs" \
  --name "Jane" --email "jane@acme.com"
```

**Lead vertical: medical / autoimmune.** In stock:
`sb-diabetes-24k` (24,000 pairs · diabetes lane · two-stream sourced + lived-experience-anchored · pre-Tribunal release),
`sb-medical-verified` (418,783 medical pairs · grading in progress),
`sb-cre-verified` (810,097 finance/CRE pairs · Atlas-class proof-of-process).
Aviation raw available on request post-audit. Autoimmune expansion, legal,
agents in development.

### The 500-Pack · signature blend

500-1,000 pairs hand-built around one failure mode. Each pair carries
`failure_source` + `repair_goal` metadata. Tribunal-sealed before delivery.
**25-50× the leverage of equivalent wholesale.**

```bash
swarmbee-bakery order --sku 500-pack \
  --domain finance \
  --failure-mode "math verification at honey confidence — refusal pattern on insufficient inputs" \
  --name "Jane" --email "jane@acme.com" \
  --notes "Atlas v2 repair, want the Tribunal seal"
```

Starter kits available: `fabrication_detection_500`, `math_verification_500`,
`recommendation_alignment_500`, `patient_comm_500`, `contract_risk_flag_500`.
Custom failure-mode scoping on intake.

## Sample packs — taste before you buy

Every domain has a free sample pack with the same provenance shape as a full
delivery. Each pack includes at least one **PROPOLIS-graded contrast pair** so
you see the rejection bar, not just the acceptance bar.

```bash
swarmbee-bakery sample finance --summary
# ─── FINANCE SAMPLE PACK (7 pairs) ───────
#   · cre-001                 [HONEY   ] avg_rubric=8.6
#     Calculate the going-in cap rate.
#   · cre-002                 [HONEY   ] avg_rubric=9.4
#     Compute DSCR for this debt structure.
#   · cre-003                 [HONEY   ] avg_rubric=9.8
#     Estimate IRR for this acquisition.
#       note: Refusal pattern. The right answer to insufficient inputs...
#   ...
#   · cre-PROPOLIS-001        [PROPOLIS] avg_rubric=0.2
#       note: INCLUDED FOR TRANSPARENCY — THIS IS WHAT WE FILTER OUT.
```

## Provenance

Every pair carries:
- `tier_grade` — APEX | HONEY | JELLY | POLLEN | PROPOLIS
- 5-dim rubric scores (1–10 each)
- `graded_at` datestamp
- `source_type`
- `tribunal_sealed` flag

Every batch carries:
- `manifest.json` with per-pair sha256
- Tribunal-seal signature (if sealed)
- Optional Hedera anchor (HCS topic `0.0.10291838`)
- Issuer signature from `swarmandbee.eth`

Outputs trained on these corpora may carry the
[**defendable.eth**](https://defendable.eth.limo) certification mark.

## Boundaries (hard rules)

The CLI **will never**:
- Submit an order without explicit `--confirm`
- Spend money or charge a card
- Create an account on your behalf
- Send messages on any platform
- Bypass any login or anti-bot mechanism

A human at Swarm & Bee reads every submission and responds within one business
day. There is no auto-submit, no spam, no upsell flow.

## Environment

```
BAKERY_BASE_URL=https://bakery.swarmandbee.ai   # default; override for testing
```

## Develop

```bash
git clone https://github.com/SudoSuOps/swarmbee-bakery
cd swarmbee-bakery
pip install -e ".[test]"
pytest -v
# Optional live tests against production:
SWARMBEE_LIVE=1 pytest -v
```

## License

MIT.

## Links

- [bakery.swarmandbee.ai](https://bakery.swarmandbee.ai) — the bakery
- [bounty.swarmandbee.ai](https://bounty.swarmandbee.ai) — broader work intake
- [identity.swarmandbee.ai](https://identity.swarmandbee.ai) — sovereign IDs
- [defendable.eth.limo](https://defendable.eth.limo) — certification standard
- `build@swarmandbee.ai` — humans, fast
