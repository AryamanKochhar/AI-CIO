from __future__ import annotations

import json
from pathlib import Path

from ai_cio.services.instruments import questions_for_client

ROOT = Path(__file__).resolve().parents[1]


def test_client_questions_omit_option_scores():
    payload = json.loads((ROOT / "instruments" / "v1.0.json").read_text())
    questions = questions_for_client(payload)
    assert len(questions) == 18
    for question in questions:
        for option in question["options"]:
            assert "score" not in option
            assert "id" in option and "text" in option
    q002 = next(q for q in questions if q["id"] == "Q002")
    assert q002["options"][0]["id"] == "1"
