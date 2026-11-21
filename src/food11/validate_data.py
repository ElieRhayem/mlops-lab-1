import argparse
import hashlib
import sys
from pathlib import Path

from PIL import Image

from src.food11.data import CLASSES

SPLITS = (
    "training",
    "validation",
    "evaluation",
)

VALID_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
}


def image_files(
    class_directory: Path,
):
    return sorted(
        path
        for path in class_directory.iterdir()
        if path.is_file()
        and path.suffix.lower()
        in VALID_EXTENSIONS
    )


def check_class_folders(
    dataset_dir: Path,
):
    errors = []

    expected = set(CLASSES)

    for split in SPLITS:
        split_dir = dataset_dir / split

        if not split_dir.exists():
            errors.append(
                f"{split}: split missing"
            )
            continue

        actual = {
            path.name
            for path in split_dir.iterdir()
            if path.is_dir()
        }

        if actual != expected:
            missing = expected - actual
            extra = actual - expected

            errors.append(
                f"{split}: "
                f"missing={sorted(missing)}, "
                f"extra={sorted(extra)}"
            )

    return errors


def check_images(
    dataset_dir: Path,
):
    errors = []

    for split in SPLITS:
        for category in CLASSES:
            class_dir = (
                dataset_dir
                / split
                / category
            )

            if not class_dir.exists():
                continue

            for path in image_files(
                class_dir
            ):
                try:
                    with Image.open(
                        path
                    ) as image:
                        image.load()

                        if image.mode != "RGB":
                            errors.append(
                                f"{path}: "
                                f"mode={image.mode}"
                            )

                        if image.size != (
                            128,
                            128,
                        ):
                            errors.append(
                                f"{path}: "
                                f"size={image.size}"
                            )

                except (OSError, ValueError) as exc:
                    errors.append(
                        f"{path}: "
                        f"cannot open ({exc})"
                    )

    return errors


def check_minimum_counts(
    dataset_dir: Path,
    minimum: int,
):
    errors = []

    for split in SPLITS:
        for category in CLASSES:
            class_dir = (
                dataset_dir
                / split
                / category
            )

            if not class_dir.exists():
                continue

            count = len(
                image_files(class_dir)
            )

            if count < minimum:
                errors.append(
                    f"{split}/{category}: "
                    f"{count} < {minimum}"
                )

    return errors


def md5(path: Path):
    return hashlib.md5(
        path.read_bytes()
    ).hexdigest()


def check_cross_split_duplicates(
    dataset_dir: Path,
):
    seen = {}
    errors = []

    for split in SPLITS:
        for category in CLASSES:
            class_dir = (
                dataset_dir
                / split
                / category
            )

            if not class_dir.exists():
                continue

            for path in image_files(
                class_dir
            ):
                digest = md5(path)

                if digest in seen:
                    previous_split, previous_path = (
                        seen[digest]
                    )

                    if previous_split != split:
                        errors.append(
                            f"{path} duplicates "
                            f"{previous_path}"
                        )
                else:
                    seen[digest] = (
                        split,
                        path,
                    )

    return errors


def class_counts(
    dataset_dir: Path,
    split: str,
):
    counts = {}

    for category in CLASSES:
        class_dir = (
            dataset_dir
            / split
            / category
        )

        counts[category] = (
            len(image_files(class_dir))
            if class_dir.exists()
            else 0
        )

    return counts


def check_distribution(
    dataset_dir: Path,
    tau: float,
):
    train_counts = class_counts(
        dataset_dir,
        "training",
    )

    validation_counts = class_counts(
        dataset_dir,
        "validation",
    )

    train_total = sum(
        train_counts.values()
    )

    validation_total = sum(
        validation_counts.values()
    )

    errors = []

    if (
        train_total == 0
        or validation_total == 0
    ):
        return [
            (
                "training or validation "
                "split is empty"
            )
        ]

    for category in CLASSES:
        train_share = (
            train_counts[category]
            / train_total
        )

        validation_share = (
            validation_counts[category]
            / validation_total
        )

        difference = abs(
            train_share
            - validation_share
        )

        if difference > tau:
            errors.append(
                f"{category}: "
                f"train={train_share:.4f}, "
                f"validation="
                f"{validation_share:.4f}, "
                f"difference="
                f"{difference:.4f} "
                f"> tau={tau}"
            )

    return errors


def report(
    name: str,
    errors: list[str],
):
    if errors:
        print(
            f"FAIL - {name}"
        )

        for error in errors:
            print(
                f"       {error}"
            )

        return False

    print(
        f"PASS - {name}"
    )

    return True


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Validate a processed "
            "Food-11 dataset."
        )
    )

    parser.add_argument(
        "dataset",
        type=Path,
    )

    parser.add_argument(
        "--min-per-class",
        type=int,
        default=50,
    )

    parser.add_argument(
        "--tau",
        type=float,
        default=0.05,
    )

    return parser.parse_args()


def main():
    args = parse_args()

    dataset_dir = (
        args.dataset.resolve()
    )

    if not dataset_dir.exists():
        print(
            f"FAIL - Dataset does not "
            f"exist: {dataset_dir}"
        )

        sys.exit(1)

    results = []

    results.append(
        report(
            "Exactly 11 class folders",
            check_class_folders(
                dataset_dir
            ),
        )
    )

    results.append(
        report(
            "Images are valid RGB 128x128",
            check_images(
                dataset_dir
            ),
        )
    )

    results.append(
        report(
            (
                "Minimum images "
                "per class"
            ),
            check_minimum_counts(
                dataset_dir,
                args.min_per_class,
            ),
        )
    )

    results.append(
        report(
            "No duplicate images "
            "across splits",
            check_cross_split_duplicates(
                dataset_dir
            ),
        )
    )

    results.append(
        report(
            "Training/validation "
            "class distribution",
            check_distribution(
                dataset_dir,
                args.tau,
            ),
        )
    )

    if all(results):
        print(
            "\nDATA CONTRACT: PASS"
        )
        sys.exit(0)

    print(
        "\nDATA CONTRACT: FAIL"
    )

    sys.exit(1)


if __name__ == "__main__":
    main()