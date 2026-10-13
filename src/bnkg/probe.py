"""Explicitly invoked, read-only instrument capture; never run automatically."""

import argparse
import json
from pathlib import Path

from bnkg.core.webxi import WebXiClient, WebXiError


def main() -> int:
    parser = argparse.ArgumentParser(description="BnKG read-only Web-XI probe (no device writes)")
    parser.add_argument("address", help="Current device IP or hostname; no saved default")
    parser.add_argument("--output", type=Path, required=True, help="New private JSON capture file")
    args = parser.parse_args()
    client = None
    try:
        if args.output.exists():
            parser.error("Output exists. Choose a new filename to preserve the previous capture.")
        client = WebXiClient(args.address)
        result = client.probe()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, ensure_ascii=False, allow_nan=False)
        print(f"Capture saved to {args.output}. Review IP/serial before sharing.")
        return 0 if not result["errors"] else 2
    except (ValueError, WebXiError, OSError) as exc:
        print(f"Probe failed: {exc}")
        return 1
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
