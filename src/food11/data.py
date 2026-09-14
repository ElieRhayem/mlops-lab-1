from pathlib import Path
import shutil

from PIL import Image


CATEGORIES = {
    0: "Bread",
    1: "Dairy product",
    2: "Dessert",
    3: "Egg",
    4: "Fried food",
    5: "Meat",
    6: "Noodles-Pasta",
    7: "Rice",
    8: "Seafood",
    9: "Soup",
    10: "Vegetable-Fruit",
}

SPLITS = ("training", "evaluation", "validation")

IMAGE_SIZE = (128, 128)
MAX_MINI_IMAGES_PER_CATEGORY = 100

# data.py is located at:
# repo_root/src/food11/data.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"

RAW_DIR = DATA_DIR / "food11_raw"
PROCESSED_DIR = DATA_DIR / "food11_processed"
MINI_DIR = DATA_DIR / "food11_processed_mini"

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def prepare_output_directories():
    """
    Delete previously generated processed datasets so that every run starts
    from a clean state, then recreate the required directory structure.
    """

    if PROCESSED_DIR.exists():
        shutil.rmtree(PROCESSED_DIR)

    if MINI_DIR.exists():
        shutil.rmtree(MINI_DIR)

    for split in SPLITS:
        for category in CATEGORIES.values():
            (PROCESSED_DIR / split / category).mkdir(
                parents=True,
                exist_ok=True,
            )

            (MINI_DIR / split / category).mkdir(
                parents=True,
                exist_ok=True,
            )


def get_category_from_filename(filename: str) -> str:
    """
    Food-11 filenames begin with the numerical class label.

    Example:
        0_123.jpg -> Bread
        5_456.jpg -> Meat
    """

    stem = Path(filename).stem
    label_text = stem.split("_", 1)[0]

    try:
        label = int(label_text)
    except ValueError as exc:
        raise ValueError(
            f"Could not determine category from filename: {filename}"
        ) from exc

    if label not in CATEGORIES:
        raise ValueError(
            f"Unknown category label {label} in file: {filename}"
        )

    return CATEGORIES[label]


def resize_and_save(source: Path, destination: Path):
    """
    Open an image, convert it to RGB, resize to 128x128,
    and save it to the requested destination.
    """

    with Image.open(source) as image:
        image = image.convert("RGB")

        image = image.resize(
            IMAGE_SIZE,
            Image.Resampling.LANCZOS,
        )

        image.save(destination)


def process_split(split: str):
    input_dir = RAW_DIR / split

    if not input_dir.exists():
        raise FileNotFoundError(
            f"Missing raw split directory: {input_dir}"
        )

    mini_counts = {
        category: 0
        for category in CATEGORIES.values()
    }

    total_processed = 0

    image_files = sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in VALID_EXTENSIONS
    )

    for image_path in image_files:
        category = get_category_from_filename(image_path.name)

        processed_destination = (
            PROCESSED_DIR
            / split
            / category
            / image_path.name
        )

        resize_and_save(
            image_path,
            processed_destination,
        )

        total_processed += 1

        # Copy no more than 100 images from each category
        # into the mini development dataset.
        if mini_counts[category] < MAX_MINI_IMAGES_PER_CATEGORY:
            mini_destination = (
                MINI_DIR
                / split
                / category
                / image_path.name
            )

            shutil.copy2(
                processed_destination,
                mini_destination,
            )

            mini_counts[category] += 1

    print(f"\n{split}:")
    print(f"  Processed images: {total_processed}")

    for category, count in mini_counts.items():
        print(f"  Mini {category}: {count}")


def main():
    if not RAW_DIR.exists():
        raise FileNotFoundError(
            f"Raw dataset was not found at: {RAW_DIR}"
        )

    print("Preparing Food-11 dataset...")
    print(f"Raw dataset: {RAW_DIR}")
    print(f"Output size: {IMAGE_SIZE[0]}x{IMAGE_SIZE[1]}")

    prepare_output_directories()

    for split in SPLITS:
        process_split(split)

    print("\nDataset preparation completed successfully.")
    print(f"Processed dataset: {PROCESSED_DIR}")
    print(f"Mini dataset: {MINI_DIR}")


if __name__ == "__main__":
    main()