#!/usr/bin/env bash
set -euo pipefail
pip install -q -r requirements.txt
exec python -m ai_cio.api
