from pathlib import Path
import argparse

import mlflow
import mlflow.pytorch
import torch
from torch import nn
from torch.optim import Adam
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from torchvision.models import resnet18, ResNet18_Weights


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"


# ---------------------------------------------------------
# Command-line arguments
# ---------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Train ResNet18 on the Food-11 dataset."
    )

    parser.add_argument(
        "--dataset",
        choices=["processed", "mini"],
        default="mini",
        help="Use food11_processed or food11_processed_mini.",
    )

    parser.add_argument(
        "--epochs",
        type=int,
        default=5,
        help="Number of training epochs.",
    )

    parser.add_argument(
        "--lr",
        type=float,
        default=0.001,
        help="Learning rate.",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size.",
    )

    return parser.parse_args()


# ---------------------------------------------------------
# Dataset and DataLoaders
# ---------------------------------------------------------

def create_dataloaders(dataset_name, batch_size):
    if dataset_name == "mini":
        dataset_dir = DATA_ROOT / "food11_processed_mini"
    else:
        dataset_dir = DATA_ROOT / "food11_processed"

    if not dataset_dir.exists():
        raise FileNotFoundError(
            f"Dataset directory does not exist: {dataset_dir}\n"
            "Run dvc pull or verify your Lab 1 data preparation."
        )

    train_dir = dataset_dir / "training"
    validation_dir = dataset_dir / "validation"
    evaluation_dir = dataset_dir / "evaluation"

    for directory in (train_dir, validation_dir, evaluation_dir):
        if not directory.exists():
            raise FileNotFoundError(
                f"Required dataset split not found: {directory}"
            )

    # The images were already resized to 128x128 in Lab 1.
    # We keep them at that size and normalize using ImageNet statistics
    # because the model uses pretrained ImageNet weights.
    image_transform = transforms.Compose(
        [
            transforms.Resize((128, 128)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )

    train_dataset = datasets.ImageFolder(
        train_dir,
        transform=image_transform,
    )

    validation_dataset = datasets.ImageFolder(
        validation_dir,
        transform=image_transform,
    )

    evaluation_dataset = datasets.ImageFolder(
        evaluation_dir,
        transform=image_transform,
    )

    # Make sure all three splits have the same category mapping.
    if not (
        train_dataset.class_to_idx
        == validation_dataset.class_to_idx
        == evaluation_dataset.class_to_idx
    ):
        raise ValueError(
            "Class mappings are not identical across "
            "training, validation, and evaluation splits."
        )

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
    )

    validation_loader = DataLoader(
        validation_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )

    evaluation_loader = DataLoader(
        evaluation_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )

    return (
        train_loader,
        validation_loader,
        evaluation_loader,
        train_dataset.classes,
    )


# ---------------------------------------------------------
# Model
# ---------------------------------------------------------

def create_model(num_classes):
    weights = ResNet18_Weights.DEFAULT

    model = resnet18(weights=weights)

    input_features = model.fc.in_features

    model.fc = nn.Linear(
        input_features,
        num_classes,
    )

    return model


# ---------------------------------------------------------
# Training
# ---------------------------------------------------------

def train_one_epoch(
    model,
    loader,
    criterion,
    optimizer,
    device,
):
    model.train()

    running_loss = 0.0
    total_samples = 0

    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()

        outputs = model(images)

        loss = criterion(outputs, labels)

        loss.backward()
        optimizer.step()

        batch_size = images.size(0)

        running_loss += loss.item() * batch_size
        total_samples += batch_size

    return running_loss / total_samples


# ---------------------------------------------------------
# Validation / evaluation
# ---------------------------------------------------------

def evaluate(
    model,
    loader,
    criterion,
    device,
):
    model.eval()

    running_loss = 0.0
    total_samples = 0
    correct_predictions = 0

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)

            outputs = model(images)
            loss = criterion(outputs, labels)

            _, predictions = torch.max(outputs, 1)

            batch_size = images.size(0)

            running_loss += loss.item() * batch_size
            total_samples += batch_size

            correct_predictions += (
                predictions == labels
            ).sum().item()

    average_loss = running_loss / total_samples

    accuracy = correct_predictions / total_samples

    return average_loss, accuracy


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():
    args = parse_args()

    # -----------------------------------------------------
    # MLflow configuration
    # -----------------------------------------------------

    mlflow.set_tracking_uri(
        "http://127.0.0.1:5000"
    )

    mlflow.set_experiment(
        "food11"
    )

    # -----------------------------------------------------
    # Device
    # -----------------------------------------------------

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print(f"Using device: {device}")

    # -----------------------------------------------------
    # Data
    # -----------------------------------------------------

    (
        train_loader,
        validation_loader,
        evaluation_loader,
        classes,
    ) = create_dataloaders(
        args.dataset,
        args.batch_size,
    )

    print(f"Classes ({len(classes)}):")
    for index, category in enumerate(classes):
        print(f"  {index}: {category}")

    print(
        f"Training images: "
        f"{len(train_loader.dataset)}"
    )

    print(
        f"Validation images: "
        f"{len(validation_loader.dataset)}"
    )

    print(
        f"Evaluation images: "
        f"{len(evaluation_loader.dataset)}"
    )

    # -----------------------------------------------------
    # Model
    # -----------------------------------------------------

    model = create_model(
        num_classes=len(classes)
    )

    model = model.to(device)

    criterion = nn.CrossEntropyLoss()

    optimizer = Adam(
        model.parameters(),
        lr=args.lr,
    )

    # -----------------------------------------------------
    # MLflow run
    # -----------------------------------------------------

    with mlflow.start_run() as run:

        print(
            f"\nMLflow Run ID: "
            f"{run.info.run_id}\n"
        )

        # Hyperparameters remain fixed for this run.
        mlflow.log_params(
            {
                "dataset": args.dataset,
                "epochs": args.epochs,
                "lr": args.lr,
                "batch_size": args.batch_size,
                "architecture": "resnet18",
                "num_classes": len(classes),
                "image_size": "128x128",
                "device": str(device),
            }
        )

        # -------------------------------------------------
        # Epoch loop
        # -------------------------------------------------

        for epoch in range(
            1,
            args.epochs + 1,
        ):
            train_loss = train_one_epoch(
                model,
                train_loader,
                criterion,
                optimizer,
                device,
            )

            (
                val_loss,
                val_accuracy,
            ) = evaluate(
                model,
                validation_loader,
                criterion,
                device,
            )

            print(
                f"Epoch "
                f"{epoch}/{args.epochs} | "
                f"train_loss={train_loss:.4f} | "
                f"val_loss={val_loss:.4f} | "
                f"val_accuracy={val_accuracy:.4f}"
            )

            # Metrics can change from epoch to epoch,
            # therefore the epoch number is recorded
            # as the MLflow metric step.
            mlflow.log_metric(
                "train_loss",
                train_loss,
                step=epoch,
            )

            mlflow.log_metric(
                "val_loss",
                val_loss,
                step=epoch,
            )

            mlflow.log_metric(
                "val_accuracy",
                val_accuracy,
                step=epoch,
            )

        # -------------------------------------------------
        # Final evaluation
        # -------------------------------------------------

        (
            test_loss,
            test_accuracy,
        ) = evaluate(
            model,
            evaluation_loader,
            criterion,
            device,
        )

        print(
            f"\nFinal evaluation loss: "
            f"{test_loss:.4f}"
        )

        print(
            f"Final test accuracy: "
            f"{test_accuracy:.4f}"
        )

        mlflow.log_metric(
            "test_loss",
            test_loss,
        )

        mlflow.log_metric(
            "test_accuracy",
            test_accuracy,
        )

        # Lab requirement:
        # save the trained PyTorch model as an MLflow artifact.
        mlflow.pytorch.log_model(
            model,
            name="model",
            serialization_format="pickle",
        )

        print(
            f"\nTraining completed."
        )

        print(
            f"Run ID: {run.info.run_id}"
        )


if __name__ == "__main__":
    main()