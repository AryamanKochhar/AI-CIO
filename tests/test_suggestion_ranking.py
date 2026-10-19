from ai_cio.services.suggestion_ranking import rank_suggestions


def test_risk_precedes_theme_and_probabilities_are_not_claimed():
    ranked = rank_suggestions([
        {"title": "Theme", "kind": "sector", "source": "rules"},
        {"title": "Concentration", "kind": "risk", "source": "rules"},
        {"title": "Model prose", "kind": "risk", "source": "ai"},
    ])
    assert [item["title"] for item in ranked] == ["Concentration", "Model prose", "Theme"]
    assert [item["rank"] for item in ranked] == [1, 2, 3]
    assert round(sum(item["relative_support_percent"] for item in ranked), 2) == 100
    assert all(item["calibrated_probability"] is False for item in ranked)


def test_ties_are_stable_and_exact_rounding_empty_is_supported():
    rows = [{"title": str(i), "source": "rules"} for i in range(3)]
    ranked = rank_suggestions(rows)
    assert [item["title"] for item in ranked] == ["0", "1", "2"]
    assert [item["relative_support_percent"] for item in ranked] == [33.34, 33.33, 33.33]
    assert rank_suggestions([]) == []
    assert rows == [{"title": str(i), "source": "rules"} for i in range(3)]
