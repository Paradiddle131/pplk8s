"""#446: each case's reach per setup, from the tables its expected SQL reads."""

from semantic_agent import bet_reach
from semantic_agent.evaluation import Question

GOLD = Question.single("g", "Revenue?", "select sum(x) from gold.daily_sales", ["revenue_eur"])
SILVER = Question.single("s", "Repliers?", "select count(*) from silver.outreach_replies", [])
CALLS = Question.single("c", "Calls?", "select count(*) from silver.call_transcripts", [])
LINEAGE = {"gold.daily_sales": ["silver.orders"]}


def test_a_derived_table_is_in_reach_through_its_silver_sources():
    assert bet_reach.reaches("native-kc", GOLD, ["covered"], LINEAGE)
    assert not bet_reach.reaches("native-graph", SILVER, ["uncovered"], LINEAGE)
    # Without its lineage a gold table is out of a silver-only agent's reach.
    assert not bet_reach.reaches("native-kc", GOLD, ["covered"], {})


def test_the_sql_setups_and_native_mcp_reach_silver_since_the_grant():
    for setup in ("baseline", "custom-hybrid", "native-mcp", "cc-native-mcp"):
        assert bet_reach.reaches(setup, CALLS, ["uncovered"], LINEAGE)
    assert not bet_reach.reaches("native-context", CALLS, ["uncovered"], LINEAGE)


def test_a_metric_setup_reaches_what_a_metric_answers():
    assert bet_reach.reaches("custom-metricflow", GOLD, ["covered"])
    assert not bet_reach.reaches("custom-metricflow", SILVER, ["composable"])
    assert bet_reach.reaches("custom-metricflow-compute", SILVER, ["composable"])
    assert not bet_reach.reaches("cc-metricflow-compute", SILVER, ["uncovered"])


def test_a_setup_without_declared_reach_is_unlabelled():
    assert bet_reach.reaches("native-governed", SILVER, ["uncovered"]) is None
    limits = bet_reach.reach_limits([GOLD, SILVER], {"g": ["covered"], "s": ["uncovered"]}, LINEAGE)
    assert limits["custom-metricflow"] == ["s"] and "baseline" not in limits
