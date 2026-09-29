from ai_cio.services.data_quality import build_data_quality_report


def test_data_quality_marks_incomplete_and_cost_basis():
    report = build_data_quality_report(
        twin={
            "completeness": {
                "psychometric": True,
                "income": True,
                "expenses": False,
                "liquid": True,
                "goals": True,
                "portfolio": True,
                "horizon": False,
            },
            "portfolio": {},
            "provenance": {},
        },
        tax_intelligence={
            "available": True,
            "data_quality": {"usable_cost_lots": 2, "insufficient": 3},
            "missing_data": ["equity_cost_basis"],
        },
        trajectory_intelligence={"behavior": {"available": False, "missing_data": ["transaction_history"]}},
    )
    assert report["available"] is True
    assert report["counts"]["incomplete"] >= 1
    assert "cost basis" in (report["confidence_note"] or "").lower() or "medium" in (
        report["confidence_note"] or ""
    ).lower()
