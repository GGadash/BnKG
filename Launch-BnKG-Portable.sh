#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ -x ./BnKG ]; then
    exec ./BnKG --data-dir "$PWD/data" "$@"
fi
exec ./.venv/bin/python BnKG_Run_Python.py --data-dir "$PWD/data" "$@"
