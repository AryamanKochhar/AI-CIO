"""Legacy entrypoint. The canonical API is `python -m ai_cio.api`."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_cio.api.main import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run("ai_cio.api.main:app", host=host, port=port, reload=False)
