import argparse
import math
import os
from pathlib import Path

import mlflow
from mlflow import MlflowClient

MODEL_NAME = "food11"

DEFAULT_TEST_DIR = Path(
    "data/food11_processed_mini/evaluation"
)

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
}


def count_test_images(
    directory: Path,
) -> int:
    return sum(
        1
        for path in directory.rglob("*")
        if path.is_file()
        and path.suffix.lower()
        in IMAGE_EXTENSIONS
    )


def get_accuracy(
    client: MlflowClient,
    run_id: str,
    metric_name: str,
) -> float:
    run = client.get_run(run_id)

    if metric_name not in run.data.metrics:
        raise ValueError(
            f"Metric '{metric_name}' "
            f"was not found in run "
            f"{run_id}."
        )

    return float(
        run.data.metrics[
            metric_name
        ]
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Apply a statistical "
            "quality gate to a "
            "Food-11 model version."
        )
    )

    parser.add_argument(
        "--version",
        required=True,
        type=int,
    )

    parser.add_argument(
        "--model-name",
        default=MODEL_NAME,
    )

    parser.add_argument(
        "--metric",
        default="test_accuracy",
    )

    parser.add_argument(
        "--test-dir",
        type=Path,
        default=DEFAULT_TEST_DIR,
    )

    return parser.parse_args()


def main():
    args = parse_args()

    tracking_uri = os.getenv(
        "MLFLOW_TRACKING_URI",
        "http://127.0.0.1:5000",
    )

    mlflow.set_tracking_uri(
        tracking_uri
    )

    client = MlflowClient()

    candidate = client.get_model_version(
        args.model_name,
        str(args.version),
    )

    champion = (
        client.get_model_version_by_alias(
            args.model_name,
            "champion",
        )
    )

    candidate_accuracy = get_accuracy(
        client,
        candidate.run_id,
        args.metric,
    )

    champion_accuracy = get_accuracy(
        client,
        champion.run_id,
        args.metric,
    )

    test_size = count_test_images(
        args.test_dir
    )

    if test_size <= 0:
        raise ValueError(
            f"No test images found in "
            f"{args.test_dir}"
        )

    se = math.sqrt(
        champion_accuracy
        * (1.0 - champion_accuracy)
        / test_size
    )

    margin = 2.0 * se

    required_accuracy = (
        champion_accuracy
        + margin
    )

    if (
        candidate_accuracy
        >= required_accuracy
    ):
        decision = (
            "promoted_to_champion"
        )

        client.set_registered_model_alias(
            args.model_name,
            "champion",
            candidate.version,
        )

    else:
        decision = (
            "assigned_challenger"
        )

        client.set_registered_model_alias(
            args.model_name,
            "challenger",
            candidate.version,
        )

    tags = {
        "promotion_decision": decision,
        "candidate_test_accuracy": (
            f"{candidate_accuracy:.6f}"
        ),
        "champion_test_accuracy_before": (
            f"{champion_accuracy:.6f}"
        ),
        "test_size": str(test_size),
        "standard_error": (
            f"{se:.6f}"
        ),
        "two_standard_errors": (
            f"{margin:.6f}"
        ),
        "required_accuracy": (
            f"{required_accuracy:.6f}"
        ),
        "evaluated_against_champion_version": (
            str(champion.version)
        ),
    }

    for key, value in tags.items():
        client.set_model_version_tag(
            args.model_name,
            candidate.version,
            key,
            value,
        )

    print(
        "=== MODEL PROMOTION GATE ==="
    )

    print(
        f"Candidate version: "
        f"{candidate.version}"
    )

    print(
        f"Champion version before gate: "
        f"{champion.version}"
    )

    print(
        f"Candidate accuracy: "
        f"{candidate_accuracy:.6f}"
    )

    print(
        f"Champion accuracy: "
        f"{champion_accuracy:.6f}"
    )

    print(
        f"Test size: {test_size}"
    )

    print(
        f"Standard error: "
        f"{se:.6f}"
    )

    print(
        f"2 * SE: "
        f"{margin:.6f}"
    )

    print(
        f"Required candidate accuracy: "
        f"{required_accuracy:.6f}"
    )

    print(
        f"Decision: {decision}"
    )


if __name__ == "__main__":
    main()