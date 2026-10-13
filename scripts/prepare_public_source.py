"""Stage a fresh curated source checkout; keep private workspace/history intact."""

import argparse
from pathlib import Path

from release_content import ROOT, public_source

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    destination = args.destination.resolve()
    if destination == ROOT or ROOT.is_relative_to(destination):
        raise SystemExit("Choose a separate staging directory.")
    public_source(destination)
    print(destination)
