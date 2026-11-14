"""The bet's custom-hybrid arm (#373): MetricFlow first, then a SQL fallback that says so."""

from semantic_agent import bet_eval, hybrid


def test_the_hybrid_drops_the_sql_ban_and_the_decline_for_the_fallback(monkeypatch):
    monkeypatch.setattr(hybrid, "tables", lambda _catalog: ["gold.daily_sales"])
    monkeypatch.setattr(hybrid, "catalog", lambda: None)
    text = hybrid.instruction(extra_tables=("legacy.country_sales",))
    assert "never write SQL" not in text
    assert "say that the semantic layer has no such metric" not in text
    assert "execute_sql tool over these tables:\ngold.daily_sales, legacy.country_sales." in text
    assert 'Begin that answer with "Not a governed metric:"' in text
    assert text.startswith(hybrid.METRICS_FIRST.splitlines()[0])


def test_the_fallback_phrase_is_a_hedge_the_set_lists():
    assert "not a governed" in [h.lower() for h in bet_eval.load_set().hedges]


def test_the_hybrid_has_the_metric_tools_and_execute_sql():
    agent = hybrid.build_agent(model="openrouter/stub:free")
    names = {getattr(t, "name", "") for t in agent.tools}
    assert {"list_metrics", "query_metrics", "execute_sql"} <= names
    assert bet_eval.RUNG["custom-hybrid"] == 4 and "custom-hybrid" in bet_eval.LEGACY_REACH
