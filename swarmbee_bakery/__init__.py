"""swarmbee-bakery — CLI for the Swarm & Bee dataset bakery.

Order curated AI training corpora from the terminal. Same backend as the
form at https://bakery.swarmandbee.ai, with structured `--sku` / `--domain`
/ `--failure-mode` flags.

Public API:
    from swarmbee_bakery import client, order
    menu = client.fetch_menu()
    pack = client.fetch_sample("finance")
"""
__version__ = "0.1.4"
__author__ = "Swarm and Bee LLC"
__url__ = "https://bakery.swarmandbee.ai"
