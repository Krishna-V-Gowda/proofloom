from dataclasses import replace

from proofloom.data import generate_hero_dataset
from proofloom.domain import DecisionStatus, MatchMethod
from proofloom.engine import CloseEngine, normalize_webhooks
from proofloom.intelligence import AmbiguityModel
from proofloom.policy import PolicyConfig


def _engine(model=None):
    model = model or AmbiguityModel.default()
    return CloseEngine(model=model, config=PolicyConfig(auto_match_threshold=max(model.threshold, 0.995), review_threshold=0.50, minimum_score_margin=0.0))


def test_event_normalization_deduplicates_and_exposes_out_of_order_delivery():
    normalized = normalize_webhooks(generate_hero_dataset().webhooks)
    assert len(normalized.accepted) == 85
    assert len(normalized.duplicate_event_ids) == 1
    assert normalized.out_of_order_event_ids


def test_hero_close_exercises_exact_split_review_and_block():
    result = _engine().run(generate_hero_dataset())
    decisions = {item.settlement_id: item for item in result.decisions}
    assert decisions["set_demo_01"].status is DecisionStatus.AUTO_MATCHED
    assert decisions["set_demo_01"].method is MatchMethod.EXACT_REFERENCE
    assert decisions["set_demo_03"].status is DecisionStatus.AUTO_MATCHED
    assert decisions["set_demo_03"].method is MatchMethod.SPLIT_SUM
    assert decisions["set_demo_02"].status is DecisionStatus.REVIEW_REQUIRED
    assert decisions["set_demo_02"].method is MatchMethod.MODEL_RANKED
    assert decisions["set_demo_04"].status is DecisionStatus.BLOCKED
    assert decisions["set_demo_04"].expected_amount_paise - decisions["set_demo_04"].observed_amount_paise == 137
    assert result.audit_valid


def test_model_outage_keeps_deterministic_paths_and_abstains_on_ambiguity():
    model = AmbiguityModel.default()
    model.available = False
    result = _engine(model).run(generate_hero_dataset())
    decisions = {item.settlement_id: item for item in result.decisions}
    assert decisions["set_demo_01"].status is DecisionStatus.AUTO_MATCHED
    assert decisions["set_demo_03"].status is DecisionStatus.AUTO_MATCHED
    assert decisions["set_demo_02"].status is DecisionStatus.UNRESOLVED
    assert decisions["set_demo_04"].status is DecisionStatus.BLOCKED


def test_wrong_direction_cannot_own_settlement():
    data = generate_hero_dataset()
    wrong = replace(data.bank_lines[0], direction=type(data.bank_lines[0].direction).DEBIT)
    data = replace(data, bank_lines=(wrong,) + data.bank_lines[1:])
    result = _engine().run(data)
    first = next(item for item in result.decisions if item.settlement_id == "set_demo_01")
    assert first.status is not DecisionStatus.AUTO_MATCHED
