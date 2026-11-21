import io
import os
from contextlib import asynccontextmanager
from typing import Annotated

import mlflow.pyfunc
import numpy as np
from fastapi import (
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)
from PIL import Image
from torchvision import transforms

import mlflow
from src.food11.data import CLASSES

MODEL_URI = os.getenv(
    "MODEL_URI",
    "models:/food11@champion",
)


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


model = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model

    if os.environ.get("SKIP_MODEL"):
        print(
            "SKIP_MODEL is set. "
            "Skipping MLflow model loading."
        )

        yield

        model = None
        return

    tracking_uri = os.getenv(
        "MLFLOW_TRACKING_URI",
        "http://127.0.0.1:5000",
    )

    print(
        f"MLflow tracking URI: "
        f"{tracking_uri}"
    )

    print(
        f"Loading model: {MODEL_URI}"
    )

    mlflow.set_tracking_uri(
        tracking_uri
    )

    model = mlflow.pyfunc.load_model(
        MODEL_URI
    )

    print(
        "Model loaded successfully."
    )

    yield

    model = None


app = FastAPI(
    title="Food-11 Classification API",
    description=(
        "Classifies Food-11 images."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {
        "status": "ok",
    }


@app.post("/predict")
async def predict(
    file: Annotated[
        UploadFile,
        File(...),
    ],
):
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Model is not loaded.",
        )

    try:
        contents = await file.read()

        image = Image.open(
            io.BytesIO(contents)
        ).convert("RGB")

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "The uploaded file is "
                "not a valid image."
            ),
        ) from exc

    image_tensor = image_transform(
        image
    )

    batch = (
        image_tensor
        .unsqueeze(0)
        .numpy()
        .astype(np.float32)
    )

    try:
        raw_prediction = model.predict(
            batch
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Model inference failed: "
                f"{exc}"
            ),
        ) from exc

    logits = np.asarray(
        raw_prediction,
        dtype=np.float32,
    )

    if logits.ndim == 2:
        logits = logits[0]

    shifted_logits = (
        logits - np.max(logits)
    )

    exp_logits = np.exp(
        shifted_logits
    )

    probabilities = (
        exp_logits
        / np.sum(exp_logits)
    )

    predicted_index = int(
        np.argmax(probabilities)
    )

    confidence = float(
        probabilities[predicted_index]
    )

    return {
        "category": CLASSES[
            predicted_index
        ],
        "confidence": confidence,
    }