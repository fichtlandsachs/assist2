#!/usr/bin/env python3
"""
Seed Salesforce documentation sources into the ExternalSource registry.

Usage:
    python scripts/seed_salesforce_sources.py [--api-url URL] [--token TOKEN] [--ingest]

Options:
    --api-url   Base URL of the HeyKarl API  (default: http://localhost:8000)
    --token     Bearer token for authentication
    --ingest    Immediately trigger ingest for each registered source
    --dry-run   Print the payloads without sending requests
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

FIXTURE = Path(__file__).parent.parent / "fixtures" / "salesforce_sources.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--api-url", default="http://localhost:8000", help="HeyKarl API base URL")
    p.add_argument("--token", default="", help="Bearer token")
    p.add_argument("--ingest", action="store_true", help="Trigger ingest after registration")
    p.add_argument("--dry-run", action="store_true", help="Print payloads, do not send")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    sources = json.loads(FIXTURE.read_text())

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"

    registered: list[str] = []
    errors: list[str] = []

    with httpx.Client(base_url=args.api_url, headers=headers, timeout=30.0) as client:
        for src in sources:
            key = src["source_key"]
            print(f"\n{'='*60}")
            print(f"  Source: {src['display_name']}  [{key}]")

            if args.dry_run:
                print(json.dumps(src, indent=2))
                continue

            # Create or skip if already exists
            resp = client.post("/api/v1/external-sources", json=src)
            if resp.status_code == 409:
                print(f"  ↩  Already registered, skipping.")
                # Still fetch id for optional ingest
                list_resp = client.get("/api/v1/external-sources")
                if list_resp.is_success:
                    existing = next(
                        (s for s in list_resp.json() if s["source_key"] == key), None
                    )
                    source_id = existing["id"] if existing else None
                else:
                    source_id = None
            elif resp.is_success:
                source_id = resp.json()["id"]
                print(f"  ✓  Registered  (id={source_id})")
                registered.append(key)
            else:
                print(f"  ✗  Error {resp.status_code}: {resp.text[:200]}")
                errors.append(key)
                continue

            # Optionally trigger ingest
            if args.ingest and source_id:
                ingest_resp = client.post(f"/api/v1/external-sources/{source_id}/ingest")
                if ingest_resp.is_success:
                    run_id = ingest_resp.json().get("run_id", "?")
                    print(f"  🚀  Ingest triggered  (run_id={run_id})")
                else:
                    print(f"  ⚠  Ingest failed: {ingest_resp.status_code} {ingest_resp.text[:200]}")

    print(f"\n{'='*60}")
    print(f"Done.  Registered: {len(registered)}  Errors: {len(errors)}")
    if errors:
        print(f"Failed sources: {', '.join(errors)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
