from __future__ import annotations

import json
import re
from pathlib import Path
from statistics import median

import pytest
import yaml

REPOSITORY = Path(__file__).resolve().parents[1]
CASES_FILE = REPOSITORY / "evals" / "held_out.json"
CUSTOM_SKILLS = (
    "business-pulse",
    "cost-investigator",
    "solution-planner",
    "technical-answer",
    "workload-radar",
)
NON_SUCCESS_STATES = {"FAILED", "TIMED_OUT", "CANCELLED", "ERROR"}


def load_cases() -> list[dict]:
    return json.loads(CASES_FILE.read_text(encoding="utf-8"))["cases"]


def case(case_id: str) -> dict:
    return next(item for item in load_cases() if item["id"] == case_id)


def skill_texts(skill_name: str) -> list[str]:
    paths = [
        REPOSITORY / "skills" / skill_name / "SKILL.md",
        REPOSITORY / "other-runtimes" / "cursor" / skill_name / "SKILL.md",
        REPOSITORY / "other-runtimes" / "claude-code" / skill_name / "SKILL.md",
    ]
    return [path.read_text(encoding="utf-8") for path in paths]


def number_pattern(value: float) -> re.Pattern[str]:
    whole = int(value) if float(value).is_integer() else None
    literal = str(whole) if whole is not None else f"{value:g}"
    suffix = r"(?:\.0+)?" if whole is not None else r"0*"
    return re.compile(rf"(?<![\d.]){re.escape(literal)}{suffix}(?![\d])")


def assert_absent_from_skill(skill_name: str, values: list[float]) -> None:
    for text in skill_texts(skill_name):
        for value in values:
            assert not number_pattern(value).search(text), (skill_name, value)


def test_every_custom_skill_has_one_held_out_and_one_missing_input_case() -> None:
    cases = load_cases()
    assert len({item["id"] for item in cases}) == len(cases)
    for skill_name in CUSTOM_SKILLS:
        kinds = sorted(item["kind"] for item in cases if item["skill"] == skill_name)
        assert kinds == ["held-out", "missing-input"], skill_name


@pytest.mark.parametrize("item", load_cases(), ids=lambda item: item["id"])
def test_case_prompts_are_safe_and_invoke_their_skill(item: dict) -> None:
    prompt = item["prompt"]
    assert prompt.startswith(f"/{item['skill']} ")
    assert "Do not run SQL." in prompt
    assert "synthetic" not in prompt.casefold()
    assert item["must"]


@pytest.mark.parametrize(
    "item",
    [item for item in load_cases() if item["kind"] == "missing-input"],
    ids=lambda item: item["id"],
)
def test_missing_input_prompts_do_not_supply_the_answer(item: dict) -> None:
    for token in item["must_not_contain"]:
        assert token not in item["prompt"]
    assert not re.search(r"\d+\s+(?:units|seconds|USD)", item["prompt"])


def test_cost_investigator_held_out_expectations() -> None:
    item = case("cost-investigator-held-out")
    usage, prices = item["input"]["usage"], item["input"]["prices"]
    expected = item["expected"]

    net: dict[str, float] = {}
    for row in usage:
        net[row["sku"]] = net.get(row["sku"], 0) + row["quantity"]
    cost = {sku: net[sku] * prices[sku]["effective_list"] for sku in net if sku in prices}
    default_cost = sum(net[sku] * prices[sku]["default"] for sku in cost)
    kept = [row for row in usage if row["record_type"] != "RETRACTION"]
    gross = {sku: sum(row["quantity"] for row in kept if row["sku"] == sku) for sku in cost}
    no_retraction_cost = sum(gross[sku] * prices[sku]["effective_list"] for sku in cost)

    assert net == expected["net_units"]
    assert cost == pytest.approx(expected["estimated_cost_usd"])
    assert sorted(set(net) - set(prices)) == expected["unmatched_skus"]
    assert sum(cost.values()) == pytest.approx(expected["total_priced_usd"])
    assert default_cost == pytest.approx(item["wrong_answers"]["priced_with_default_key_usd"])
    assert no_retraction_cost == pytest.approx(item["wrong_answers"]["ignored_retraction_usd"])
    for row in usage:
        assert f"{row['sku']} {row['record_type']} {row['quantity']} units" in item["prompt"]

    assert_absent_from_skill(
        "cost-investigator",
        [*expected["estimated_cost_usd"].values(), expected["total_priced_usd"], 0.75],
    )
    for text in skill_texts("cost-investigator"):
        assert "SKU_M" not in text


def test_workload_radar_held_out_expectations() -> None:
    item = case("workload-radar-held-out")
    prior, current = item["input"]["prior"], item["input"]["current"]
    expected = item["expected"]

    def non_success(window: dict) -> int:
        return sum(state in NON_SUCCESS_STATES for state in window["states"])

    assert [len(prior["durations"]), len(current["durations"])] == expected["runs"]
    assert [median(prior["durations"]), median(current["durations"])] == expected["median_seconds"]
    assert [non_success(prior), non_success(current)] == expected["non_success"]
    assert [prior["retries"], current["retries"]] == expected["retries"]
    assert [prior["cost_usd"], current["cost_usd"]] == expected["cost_usd"]
    change = (current["cost_usd"] - prior["cost_usd"]) / prior["cost_usd"] * 100
    assert change == pytest.approx(expected["cost_change_pct"])
    mean = sum(current["durations"]) / len(current["durations"])
    assert mean == pytest.approx(item["wrong_answers"]["current_mean_seconds"])
    for duration in prior["durations"] + current["durations"]:
        assert str(duration) in item["prompt"]

    assert_absent_from_skill("workload-radar", [525, 65, 532.5])
    for text in skill_texts("workload-radar"):
        assert "job_x" not in text


def test_business_pulse_held_out_expectations() -> None:
    item = case("business-pulse-held-out")
    prior, current = item["input"]["prior"], item["input"]["current"]
    expected = item["expected"]

    prior_total, current_total = sum(prior.values()), sum(current.values())
    contributions = {
        city: current.get(city, 0) - prior.get(city, 0) for city in sorted({*prior, *current})
    }
    ranked = sorted(contributions.items(), key=lambda pair: -abs(pair[1]))

    assert prior_total == expected["prior_total"]
    assert current_total == expected["current_total"]
    assert current_total - prior_total == expected["delta"]
    assert sum(contributions.values()) == expected["delta"]
    change = (current_total - prior_total) / prior_total * 100
    assert change == pytest.approx(expected["delta_pct"])
    assert [list(pair) for pair in ranked] == expected["contributions_ranked"]
    for window in (prior, current):
        for city, value in window.items():
            assert f"{city} {value}" in item["prompt"]

    assert_absent_from_skill("business-pulse", [800, 890, expected["delta_pct"], 45])
    for text in skill_texts("business-pulse"):
        for city in contributions:
            assert city not in text


def test_technical_answer_held_out_fact_is_not_in_the_skill() -> None:
    expected = case("technical-answer-held-out")["expected"]
    assert expected["source"].startswith("https://docs.databricks.com/aws/en/")
    assert_absent_from_skill("technical-answer", [expected["max_entries_per_skill"]])
    for text in skill_texts("technical-answer"):
        assert expected["source"] not in text


def test_solution_planner_held_out_requirements_are_not_in_the_skill() -> None:
    item = case("solution-planner-held-out")
    assert item["expected"]["alternatives"] == 1
    for text in skill_texts("solution-planner"):
        assert "06:00 UTC" not in text
        assert "2 GB per day" not in text


@pytest.mark.parametrize("skill_name", CUSTOM_SKILLS)
def test_genie_skill_declares_requirements_and_opt_in_sample(skill_name: str) -> None:
    text = (REPOSITORY / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
    header = yaml.safe_load(text.split("---", 2)[1])

    assert 0 < len(header["compatibility"]) <= 500
    assert "## Who this is for" in text
    assert "## Requirements" in text
    assert "## Missing or ambiguous input" in text
    assert "Genie Agents" not in text
    assert "fallback" not in text.casefold()
    if "## Built-in sample (only on request)" in text:
        assert "only when the user asks for a `sample` or `demo`" in text
        assert "do not show sample numbers" in text


@pytest.mark.parametrize("skill_name", CUSTOM_SKILLS)
def test_skill_page_quotes_the_exact_test_prompts(skill_name: str) -> None:
    page = (REPOSITORY / "docs" / "skills" / f"{skill_name}.md").read_text(encoding="utf-8")
    for item in load_cases():
        if item["skill"] == skill_name:
            assert item["prompt"] in page, item["id"]


def test_cost_skills_price_with_the_effective_list_key() -> None:
    for skill_name in ("cost-investigator", "workload-radar"):
        for text in skill_texts(skill_name):
            assert "pricing.effective_list.default" in text
            assert "pricing.default AS" not in text


def test_workload_radar_keeps_explicit_retries_and_heuristic_separate() -> None:
    for text in skill_texts("workload-radar"):
        assert "COUNT_IF(trigger_type = 'ONETIME_RETRY') AS explicit_retry_runs" in text
        assert "SUM(repair_like_attempts) AS repair_like_attempts_heuristic" in text
        assert "never add them together" in text
        assert "+ SUM(repair" not in text
        assert "mark only the signals that depend on it `unavailable`" in text


def test_business_pulse_separates_metric_view_measures_and_non_additive_metrics() -> None:
    for text in skill_texts("business-pulse"):
        assert text.count("MEASURE(`Metric Name`)") == 2
        assert "Never wrap a measure in `SUM`, `AVG`, or `COUNT`" in text
        assert "never use `SELECT *`" in text
        assert "The SQL below handles additive metrics only." in text
        assert "dimension changes do not add up to the total change" in text
        assert "dimension counts overlap and do not add up to the total" in text


def test_business_pulse_asks_for_metric_definition_when_only_a_name_is_given() -> None:
    text = (REPOSITORY / "skills/business-pulse/SKILL.md").read_text(encoding="utf-8")
    assert 'A metric name alone, such as "revenue" or "users", is not a definition.' in text
    assert "Ask this even when the candidate tables have a column with that name." in text


def test_business_pulse_checks_brief_length_gate_label_and_comparisons() -> None:
    for text in skill_texts("business-pulse"):
        assert "five bullets" in text
        assert "count them before answering" in text or "Before you answer, check" in text
        assert "`not applicable`" in text
        assert "matches the displayed numbers for both periods" in text or (
            "against the displayed numbers for both periods" in text
        )
        assert "rank-change words" in text
        assert '"overtook", "passed", or "became the second largest"' in text


def test_business_pulse_needs_a_baseline_for_noise_and_names_the_larger_side() -> None:
    for text in skill_texts("business-pulse"):
        assert "normal, typical, or noise unless you queried and displayed a baseline" in text
        assert "say which side is larger and show both totals" in text


def test_status_labels_include_private_preview_and_experimental() -> None:
    for skill_name in ("technical-answer", "solution-planner"):
        for text in skill_texts(skill_name):
            assert "`Private Preview`" in text
            assert "`Experimental`" in text


def test_status_labels_do_not_treat_a_missing_label_as_ga() -> None:
    for skill_name in ("technical-answer", "solution-planner"):
        for text in skill_texts(skill_name):
            assert "A page or section without a release label does not state `GA`" in text


def test_workload_radar_keeps_hedged_explanations_out_of_observations() -> None:
    for text in skill_texts("workload-radar"):
        assert '"possibly", "may", "likely", "because", or "suggests"' in text


def test_workload_radar_checks_table_freshness_before_calling_job_data_late() -> None:
    for text in skill_texts("workload-radar"):
        assert "compare it with the newest record in the whole table" in text
        assert "`no completed runs after <timestamp>`" in text


def test_workload_radar_lists_access_by_name_when_not_executed() -> None:
    for text in skill_texts("workload-radar"):
        assert "List the access needed by name" in text or "list the access needed by name" in text
        assert "`SELECT` on each table the SQL reads" in text


def test_solution_planner_asks_for_the_cloud_when_the_user_does_not_name_it() -> None:
    for text in skill_texts("solution-planner"):
        assert "The cloud counts as given only when the user names it" in text
        assert "one question must ask for it" in text


def test_solution_planner_checks_the_diagram_for_unicode_arrows() -> None:
    for text in skill_texts("solution-planner"):
        assert 'no Unicode arrows such as "→"' in text


def test_solution_planner_cites_only_in_the_status_table_and_limits_searches() -> None:
    text = (REPOSITORY / "skills/solution-planner/SKILL.md").read_text(encoding="utf-8")
    assert "next to the choice" not in text
    assert "`Smallest recommended stack`, components and roles only, without links" in text
    assert "Run at most five documentation searches" in text
    assert "put no citation markers in the data flow" in text


def test_solution_planner_requires_a_source_link_for_every_selected_product() -> None:
    for text in skill_texts("solution-planner"):
        assert "every product in the stack table has a status row with its own source link" in text


def test_solution_planner_checks_status_evidence_sources_and_length() -> None:
    for text in skill_texts("solution-planner"):
        assert "Quote the release words" in text or "quote the release words" in text
        assert "at most six distinct source" in text
        assert "under 900 words" in text
    canonical = (REPOSITORY / "skills/solution-planner/SKILL.md").read_text(encoding="utf-8")
    assert "the limit covers the chat reply and the document together" in canonical
    assert "Cite sources only in `Product status and evidence` and `Sources`" in canonical
    assert "Word budget" in canonical


def test_technical_answer_keeps_all_five_headings() -> None:
    text = (REPOSITORY / "skills/technical-answer/SKILL.md").read_text(encoding="utf-8")
    assert "all five headings, in this order, even when a section only says `Not needed`" in text


def test_technical_answer_stops_after_asking_for_the_cloud() -> None:
    for text in skill_texts("technical-answer"):
        assert "workspace, the environment, or an earlier chat" in text
        assert "ask which cloud before researching" in text
        assert "do not search" in text.lower()
    canonical = (REPOSITORY / "skills/technical-answer/SKILL.md").read_text(encoding="utf-8")
    assert "First check, before any search" in canonical
    assert canonical.index("First check, before any search") < canonical.index("## Who this is for")
