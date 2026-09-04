from proofloom.data import generate_evaluation_dataset
from proofloom.evaluation import group_predictions, run_evaluation
from proofloom.intelligence import AmbiguityModel


def test_model_training_and_threshold_are_deterministic():
    dataset = generate_evaluation_dataset()
    one = AmbiguityModel.train(dataset)
    two = AmbiguityModel.train(dataset)
    assert one.model_version == two.model_version
    assert one.threshold == two.threshold


def test_evaluation_runs_and_keeps_claim_boundary(tmp_path):
    result = run_evaluation(tmp_path, bootstrap_resamples=30)
    pair = result["pair_classifier_held_out"]
    policy = result["policy_comparison"]["proofloom_hybrid"]
    assert pair["records"] == 1008
    assert pair["pr_auc"] > 0.80
    assert policy["auto_match_precision"] >= 0.95 or policy["auto_matches"] == 0
    assert result["limitations"]
    assert (tmp_path / "predictions.csv").is_file()
    assert (tmp_path / "results.md").is_file()
