# Lab 3 - Containerizing the Model with Docker

## Model Registration

The best model from the `food11` MLflow experiment was selected based on its validation accuracy and registered in the MLflow Model Registry under the name:

```text
food11
```

The registered version was then assigned the alias:

```text
champion
```

The serving application accesses the model through:

```text
models:/food11@champion
```

---

## Question 1

### What version number was the model given? What is the difference between a logged model artifact and a registered model?

The registered model was assigned:

```text
Version: 1
```

A logged model artifact belongs to one specific MLflow training run. It represents the model produced by that particular execution and is associated with the run's parameters, metrics, and Run ID.
A registered model provides a stable logical model name, such as `food11`, and allows different versions of that model to be managed independently of individual training runs.
For example:

```text
Training Run A -> logged model -> food11 Version 1
Training Run B -> logged model -> food11 Version 2
```

## The Model Registry preserves the relationship to the originating run while providing a deployment-oriented model identity and version history.

## Question 2

### What aliases replaced the old built-in stages? Why version a model independently, and why are aliases more flexible?

Current MLflow uses model version **aliases** instead of relying on the old fixed stages such as `Staging` and `Production`.
Aliases are user-defined names. Common examples include:

```text
champion
challenger
candidate
```

For this lab I used:

```text
champion
```

Versioning the model separately from its training run provides a stable deployment identity. Training runs describe experiments, whereas registered-model versions describe model releases that may be evaluated or deployed.
An alias is more flexible than a fixed stage because it is a mutable pointer.
For example:

```text
food11 Version 1 <- champion
```

can later become:

```text
food11 Version 2 <- champion
```

without changing the model version numbers themselves.
Applications can continue loading:

```text
models:/food11@champion
```

## without needing to know which numerical model version currently represents the champion.

## Serving API

A FastAPI application was created at:
src/food11/serve.py
It provides two endpoints:
GET /health
POST /predict
GET /health returns:
{"status": "ok"}
POST /predict accepts an uploaded image, applies the same resizing and normalization used during training, runs the image through the MLflow model, and returns the predicted Food-11 category together with a confidence score.
The application keeps the model location configurable through the MODEL_URI environment variable.
When running locally, the intended MLflow Model Registry URI is:
models:/food11@champion
The MLflow tracking URI is read from the MLFLOW_TRACKING_URI environment variable and defaults to:
http://127.0.0.1:5000
For the Docker execution on my Windows machine, I mounted the logged MLflow model artifact from the host into the container as a read-only volume and set:
MODEL_URI=/model
The working container command was:
docker run --name food11-api-container -p 8000:8000 -e MLFLOW_TRACKING_URI=http://host.docker.internal:5000 -e MODEL_URI=/model -v "%cd%\mlruns\1\models\m-05907c34383941ce880afcbb3ee8f8d7\artifacts:/model:ro" food11-api:latest
This allowed the same FastAPI serving code to load the MLflow model from the mounted /model directory inside the container.

---

## Question 3

### Why use an MLflow model URI rather than a direct .pth file? What changes when a newer model should be served?

Using an MLflow model URI provides an abstraction above the physical PyTorch .pth file.
With the Model Registry URI:
models:/food11@champion
the application does not need to know the physical location of the model files or the Run ID that produced them. The champion alias can later be reassigned to another registered version without changing the serving code.
If the API referenced a .pth file directly, the application would depend on a specific local filesystem path and model file. Changing the deployed model could require changing that path or manually replacing files.
During my Docker test, I kept the model source configurable but supplied the model through:
MODEL_URI=/model
where /model was a read-only Docker volume containing the logged MLflow model artifact from the host.
Therefore, with my Docker test configuration, serving a newer model would require mounting a different MLflow model-artifact directory or changing MODEL_URI.
With the intended Model Registry configuration, serving a newer registered model would only require reassigning the champion alias to the newer model version and restarting or reloading the serving application. The code could continue using:
models:/food11@champion

---

# Docker Image

The application was packaged using a multi-stage Docker build.
The first stage is a builder stage. It installs `uv`, copies `pyproject.toml` and `uv.lock`, and recreates the locked Python environment.
The second stage starts from a slim Python image and receives only the prepared virtual environment and the application source code required at runtime.

---

## Question 4

### Why are `pyproject.toml` and `uv.lock` copied before the source code?

Docker builds images as a sequence of cached layers.
The dependency files:

```text
pyproject.toml
uv.lock
```

normally change less frequently than application source files.
The Dockerfile therefore performs:

```text
COPY pyproject.toml uv.lock
RUN uv sync
```

before:

```text
COPY src
```

If I change only a line in `serve.py`, the dependency files have not changed, so Docker can reuse the previously cached dependency-installation layer.
Only the source-code copy layer and later layers need to be rebuilt.
If all project files were copied before dependency installation, changing one source-code file could invalidate the cache and force the expensive dependency installation to run again.

---

## Question 5

### What was the size difference between the naive and multi-stage images?

I built both a multi-stage image and a temporary naive single-stage image.
The observed sizes were:

```text
Multi-stage image: 1.49 GB
Naive image:       2.56 GB
Difference:        1.07 GB
```

I inspected the layers using:

```bash
docker history food11-api:latest
docker history food11-api:naive
```

The largest layers on my machine were:

```text
COPY /app/.venv /app/.venv # buildkit
```

## The multi-stage approach prevents build-stage tools and the larger builder environment from automatically becoming part of the final runtime image. The final image contains only what is required to execute the serving API.

## Question 6

### What happens without `.dockerignore`? Which excluded directories could cause problems?

Without `.dockerignore`, unnecessary files can be included in the Docker build context.
In this project these could include:

```text
data/
mlruns/
mlflow.db
.git/
.venv/
__pycache__/
```

The Food-11 dataset and MLflow artifacts can be large, so including them in the build context increases data transfer, disk usage, and potentially build time.
The current Dockerfile uses explicit `COPY` instructions, so simply sending these additional files does not necessarily copy all of them into the final image.
However, a local `.venv` is particularly dangerous if a Dockerfile later uses `COPY . .`, because the host virtual environment was created for Windows while the Docker image runs Linux. It could overwrite or conflict with the Linux environment.
Likewise, `data/` and `mlruns/` could make an image unnecessarily large if copied using a broad `COPY . .`.
The `.dockerignore` therefore both improves build efficiency and prevents accidental inclusion of local or large generated files.

---

# Container Networking

The application running inside the Docker container needs to contact the MLflow tracking server running on the Windows host.
The container was started with:

```text
MLFLOW_TRACKING_URI=http://host.docker.internal:5000
```

## and port `8000` was published between the container and the host.

## Question 7

### Why can't the container use 127.0.0.1:5000 to contact the host MLflow server?

A Docker container has its own isolated network namespace.
Inside the container:
127.0.0.1
refers to the container itself, not to the Windows host.
Therefore, trying to contact:
http://127.0.0.1:5000
from inside the container would look for an MLflow server inside that same container.
Docker Desktop provides the special hostname:
host.docker.internal
which resolves to the Windows host from inside the container.
Therefore, a service running on the Windows host at port 5000 can be reached from the container using:
http://host.docker.internal:5000
In my final Docker execution, the model artifact itself was supplied through a read-only mounted volume at /model, while the MLflow tracking URI was still configured as:
http://host.docker.internal:5000

---

## Question 8

### Does a new container from the same image still load the model without rebuilding? What does that show?

Yes, a new container can be started from the same Docker image without rebuilding it.
However, in my working Docker configuration the trained Food-11 model is not baked into the Docker image.
The image contains:
Python runtime
project dependencies
FastAPI application
MLflow client
PyTorch
model-serving code
The model artifact is provided separately at runtime through a Docker volume:
Host MLflow model artifact
↓
Docker volume mount
↓
/model
↓
MODEL_URI=/model
↓
FastAPI application
Therefore, when starting another container from the same image, I must provide the model volume again using:
-v "...\artifacts:/model:ro"
together with:
-e MODEL_URI=/model
No Docker rebuild is required because neither the model artifact nor the specific trained model version is stored inside the image.
This demonstrates the separation between the reusable serving environment stored in the Docker image and the model supplied at runtime.
In a fully registry-based deployment, the same image could instead load:
models:/food11@champion
from MLflow at startup. In that case, reassigning the champion alias and restarting the container would allow the same image to serve a newer registered model version.

---

## Question 9

### What is still missing before another machine can reliably pull and run the exact Docker image?

The Dockerfile is versioned in Git, but the locally built Docker image currently exists only in the local Docker image store.
Another machine cannot pull:

```text
food11-api:latest
```

from my laptop automatically.
The image must first be pushed to an image registry such as:

```text
Docker Hub
GitHub Container Registry
a private container registry
```

It should also be given an immutable or uniquely identifiable version tag rather than relying only on:

```text
latest
```

For example:

```text
food11-api:1.0.0
```

or a tag based on the Git commit SHA.
For maximum reproducibility, deployment can also reference the image digest.
The complete reproducible deployment chain would therefore be:

```text
Git repository
    -> Dockerfile and application source
CI/build process
    -> builds image
Container registry
    -> stores versioned image
CI runner / Kubernetes
    -> pulls exact image tag or digest
```

## This ensures that another machine can retrieve and execute the exact container image that was built and tested.

# Conclusion

Lab 3 extends the responsibilities introduced in Labs 1 and 2:

```text
Git
-> source code and configuration
DVC
-> Food-11 dataset versions
MLflow Tracking
-> training experiments and metrics
MLflow Model Registry
-> model versions and deployment aliases
Docker
-> reproducible serving runtime
```

The deployment path is now:

```text
Food-11 data
    ↓
DVC
Training code
    ↓
PyTorch
Experiment
    ↓
MLflow run
Best logged model
    ↓
MLflow Model Registry
food11 model version
    ↓
champion alias
FastAPI
    ↓
model inference endpoint
Docker image
    ↓
portable serving environment
```
