import hashlib
import shutil
from pathlib import Path

from PIL import Image

CLASSES = [
    "Bread",
    "Dairy product",
    "Dessert",
    "Egg",
    "Fried food",
    "Meat",
    "Noodles-Pasta",
    "Rice",
    "Seafood",
    "Soup",
    "Vegetable-Fruit",
]

CATEGORIES = {
    index: category
    for index, category in enumerate(CLASSES)
}

SPLITS = (
    "training",
    "validation",
    "evaluation",
)

IMAGE_SIZE = 128
MAX_MINI_IMAGES_PER_CATEGORY = 100

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"

RAW_DIR = DATA_DIR / "food11_raw"
PROCESSED_DIR = DATA_DIR / "food11_processed"
MINI_DIR = DATA_DIR / "food11_processed_mini"

VALID_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
}


def category_from_filename(filename: str) -> str:
    """
    Convert a Food-11 filename into its category.

    Example:
        3_120.jpg -> Egg
    """

    stem = Path(filename).stem
    label_text = stem.split("_", 1)[0]

    try:
        label = int(label_text)
    except ValueError as exc:
        raise ValueError(
            f"Could not determine category from filename: "
            f"{filename}"
        ) from exc

    if label not in CATEGORIES:
        raise ValueError(
            f"Unknown category label {label} "
            f"in file: {filename}"
        )

    return CATEGORIES[label]


def resize_image(
    img: Image.Image,
    size: int = IMAGE_SIZE,
) -> Image.Image:
    """
    Convert an image to RGB and resize it
    to size x size.
    """

    return img.convert("RGB").resize(
        (size, size),
        Image.Resampling.LANCZOS,
    )


def prepare_output_directories():
    if PROCESSED_DIR.exists():
        shutil.rmtree(PROCESSED_DIR)

    if MINI_DIR.exists():
        shutil.rmtree(MINI_DIR)

    for split in SPLITS:
        for category in CLASSES:
            (
                PROCESSED_DIR
                / split
                / category
            ).mkdir(
                parents=True,
                exist_ok=True,
            )

            (
                MINI_DIR
                / split
                / category
            ).mkdir(
                parents=True,
                exist_ok=True,
            )

def file_hash(path: Path) -> str:
    return hashlib.md5(
        path.read_bytes()
    ).hexdigest()

def process_split(
    split: str,
    seen_hashes: set[str],
):
    input_dir = RAW_DIR / split

    if not input_dir.exists():
        raise FileNotFoundError(
            f"Missing raw split directory: {input_dir}"
        )

    mini_counts = {
        category: 0
        for category in CLASSES
    }

    total_processed = 0

    image_files = sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in VALID_EXTENSIONS
    )

    for image_path in image_files:
        digest = file_hash(image_path)

        if digest in seen_hashes:
            print(
                f"  Skipping duplicate: "
                f"{image_path.name}"
            )
            continue

        seen_hashes.add(digest)

        category = category_from_filename(
            image_path.name
        )
        category = category_from_filename(
            image_path.name
        )

        processed_destination = (
            PROCESSED_DIR
            / split
            / category
            / image_path.name
        )

        with Image.open(image_path) as image:
            processed_image = resize_image(image)
            processed_image.save(
                processed_destination
            )

        total_processed += 1

        if (
            mini_counts[category]
            < MAX_MINI_IMAGES_PER_CATEGORY
        ):
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
    print(
        f"  Processed images: {total_processed}"
    )

    for category, count in mini_counts.items():
        print(
            f"  Mini {category}: {count}"
        )


def main():
    if not RAW_DIR.exists():
        raise FileNotFoundError(
            f"Raw dataset was not found at: "
            f"{RAW_DIR}"
        )

    print("Preparing Food-11 dataset...")
    print(f"Raw dataset: {RAW_DIR}")
    print(
        f"Output size: "
        f"{IMAGE_SIZE}x{IMAGE_SIZE}"
    )

    prepare_output_directories()

    seen_hashes: set[str] = set()
    
    for split in SPLITS:
        process_split(
            split,
            seen_hashes,
        )

    print(
        "\nDataset preparation "
        "completed successfully."
    )

    print(
        f"Processed dataset: "
        f"{PROCESSED_DIR}"
    )

    print(
        f"Mini dataset: "
        f"{MINI_DIR}"
    )


if __name__ == "__main__":
    main()