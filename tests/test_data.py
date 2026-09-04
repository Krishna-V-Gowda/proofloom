from proofloom.data import generate_evaluation_dataset, generate_hero_dataset
from proofloom.policy import expected_net_paise


def test_hero_dataset_has_exact_official_bar_and_cases():
    data = generate_hero_dataset()
    assert len(data.payments) == 84
    assert len(data.refunds) == 6
    assert len(data.settlements) == 4
    assert len(data.bank_lines) == 5
    assert len(data.webhooks) == 86
    assert data.source_record_count == 185


def test_hero_composition_has_exact_137_paise_contradiction():
    data = generate_hero_dataset()
    by_id = {item.settlement_id: item for item in data.settlements}
    for sid in ("set_demo_01", "set_demo_02", "set_demo_03"):
        assert expected_net_paise(by_id[sid], data.payments, data.refunds) == by_id[sid].reported_amount_paise
    broken = by_id["set_demo_04"]
    assert expected_net_paise(broken, data.payments, data.refunds) - broken.reported_amount_paise == 137


def test_evaluation_split_shape_is_deterministic():
    one = generate_evaluation_dataset()
    two = generate_evaluation_dataset()
    assert one == two
    assert len(one.merchant_groups) == 24
    assert len(one.pairs) == 24 * 42 * 6
    assert sum(pair.label for pair in one.pairs) == 24 * 42
