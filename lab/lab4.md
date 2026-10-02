# Lab 4 - Orchestrating the App with Docker Compose

## Implementation Note

This lab continues the same `mlops-lab-1` project from Labs 1-3.

Current MLflow versions deprecate the old built-in Model Registry stages such as `Staging` and `Production` in favor of aliases. Therefore, for this lab I used a model version alias named:

```text
staging
```

as the modern equivalent of the lab's requested `Staging` deployment reference.

The inference service uses:

```text
models:/food11@staging
```

This preserves the intended workflow: the application refers to a stable deployment name while the model version behind that name can change.

---

## Question 1

### What happens to `/mlflow-data` without a volume?

If the MLflow container is started without mounting a volume at `/mlflow-data`, the SQLite database and model/artifact files are written into that container's writable filesystem layer.

Stopping the container does not immediately remove those files because the stopped container still exists. However, after removing that container and creating a new container from the same image, the new container starts with a fresh writable layer.

Therefore, the new MLflow UI does not contain the experiments, registered models, aliases, or artifacts that were created only inside the removed container.

The Docker image itself is unchanged and does not contain runtime data created after the container starts.

This demonstrates why persistent state should not be stored only inside the writable layer of a disposable container.

---

## Question 2

### Why use a named volume instead of a bind mount? Would a bind mount work?

A named Docker volume is suitable for MLflow's persistent state because Docker manages its storage location and lifecycle independently of any individual container.

In this lab:

```text
mlflow-data
```

stores the MLflow SQLite database and artifact data outside the MLflow container's writable layer.

This means that the MLflow container can be stopped, removed, and recreated while the data remains available.

A bind mount to a host directory would also work. For example, a host folder could be mapped to `/mlflow-data`.

However, a named volume is cleaner for this Compose stack because:

- Docker manages its location.
- The repository is not filled with runtime database/artifact files.
- It is less dependent on host-specific filesystem paths.
- It is easier to declare and reuse directly in `docker-compose.yml`.

A bind mount can be more convenient during local development when direct access to the files from the host is desirable, but it is more host-path and permission dependent.

---

## Question 3

### Why does `http://mlflow:5000` work in Compose when it did not work in Lab 3?

Docker Compose creates a private network for the services in the Compose project.

Each service is discoverable on that network by its Compose service name.

Therefore:

```text
mlflow
```

acts as a hostname that resolves to the MLflow service container.

The inference service can consequently use:

```text
http://mlflow:5000
```

to communicate directly with MLflow.

In Lab 3, the MLflow server was running on the Windows host rather than as a container in the same Docker network. The inference container therefore had to use:

```text
host.docker.internal
```

to reach the host machine.

In Lab 4, both services belong to the same Compose network, so service-name DNS replaces the host-specific address.

---

## Question 4

### Why read `INFERENCE_URL` from an environment variable?

The frontend reads the inference-service address from:

```text
INFERENCE_URL
```

instead of hardcoding:

```text
http://inference:8000
```

because `inference` is a hostname that exists specifically inside the Docker Compose network.

When the frontend runs inside Compose, the environment variable is set to:

```text
http://inference:8000
```

If the same frontend image is run directly on the host or with a standalone `docker run`, that Compose service name may not exist.

The URL can then be changed without modifying or rebuilding the frontend source code, for example to:

```text
http://127.0.0.1:8000
```

or to another deployed inference endpoint.

This makes the image reusable across different environments.

---

## Question 5

### Why does the inference service not publish a host port, and how does the frontend reach it?

The inference service is used internally by the frontend and does not need to be accessed directly by a human from the host machine in this Compose architecture.

Therefore, it does not need a mapping such as:

```text
8000:8000
```

The frontend and inference containers are on the same Docker Compose network.

The frontend reaches the API using:

```text
http://inference:8000
```

where `inference` is resolved by Compose's internal DNS to the inference container.

The traffic stays inside the Compose network.

The ports that need to be accessed directly by a user are published:

```text
5000 -> MLflow UI
8501 -> Streamlit frontend
```

---

## Question 6

### What can happen because `depends_on` controls start order but not readiness?

The short form of:

```yaml
depends_on:
  - mlflow
```

ensures that Docker Compose starts the MLflow container before it starts the inference container.

However, it does not guarantee that the MLflow server inside that container has finished initializing and is already accepting HTTP requests.

The inference application loads its model during application startup.

Therefore, if it tries to resolve:

```text
models:/food11@staging
```

before MLflow is ready, the model-loading request can fail and the inference process can exit.

This can be inspected using:

```bash
docker compose logs inference
```

Once MLflow is ready, the inference service can be restarted with:

```bash
docker compose restart inference
```

A more production-oriented solution would use a health check with a readiness condition or implement retry logic in the inference application.

---

## Question 7

### Which services publish ports according to `docker compose ps`?

The expected published ports are:

```text
mlflow
5000:5000

frontend
8501:8501
```

The inference service does not publish a port to the host.

This matches the Compose configuration.

The frontend communicates with inference internally through:

```text
http://inference:8000
```

while users access:

```text
http://127.0.0.1:5000
```

for MLflow and:

```text
http://127.0.0.1:8501
```

for the frontend.

---

## Question 8

### After assigning the deployment reference to a newer model, does the running inference service immediately use it?

No.

The inference application loads the model once when the service starts.

Changing the `staging` alias in MLflow changes which model version the alias points to, but it does not replace the model object that is already loaded in the running inference process.

Therefore, before restarting inference, requests continue to use the model that was loaded at the previous startup.

The command:

```bash
docker compose restart inference
```

starts the inference container process again.

During startup, `serve.py` resolves:

```text
models:/food11@staging
```

again and loads the model version currently assigned to the `staging` alias.

If the newly registered version contains the same underlying model as the previous version, the prediction output may be identical even though the registry version reference changed.

---

## Question 9

### Why is no image rebuild required after changing the model version?

The inference Docker image contains the application runtime, dependencies, and serving source code.

It does not contain the specific registered model version selected by the `staging` alias.

The model is resolved and loaded from MLflow when the inference application starts.

Therefore, changing the model version or reassigning the `staging` alias does not modify anything inside the Docker image.

A simple:

```bash
docker compose restart inference
```

is sufficient because the restarted process performs model loading again.

A rebuild would only be required if something baked into the image changed, such as:

- `serve.py`
- Python dependencies
- the Dockerfile
- other copied application files

---

## Question 10

### What happens after `docker compose down` compared with `docker compose down -v`?

After:

```bash
docker compose down
docker compose up
```

the registered model, experiment information, SQLite database, artifacts, and the `staging` alias remain available.

This happens because normal `docker compose down` removes the service containers and network but keeps the named volume:

```text
mlflow-data
```

When the stack starts again, the new MLflow container mounts the same persistent volume.

After:

```bash
docker compose down -v
docker compose up
```

the result is different.

The `-v` option removes the named volumes declared by the Compose project.

Therefore, the MLflow database and artifacts stored in `mlflow-data` are deleted.

The next MLflow container starts with fresh storage, so previous experiments, registered models, model versions, aliases, and artifacts are no longer present.

The inference service may also fail to load its model because:

```text
models:/food11@staging
```

no longer exists in the fresh MLflow registry.

This demonstrates that the persistence belongs to the named volume rather than to the disposable containers.

---

## Question 11

### What is missing for multiple replicas or survival of a machine failure?

Docker Compose is mainly a single-host orchestration tool.

Running three reliable inference replicas behind a load balancer, automatically rescheduling failed containers across multiple machines, and keeping MLflow available after the host machine fails require capabilities beyond this local Compose setup.

A production deployment would typically require an orchestrator such as Kubernetes or another multi-node container orchestration platform.

For the inference service, this would provide features such as:

- multiple replicas
- service discovery
- load balancing
- health checks
- automatic restart/rescheduling
- rolling deployments
- resource management

For MLflow, machine-failure resilience would also require persistent storage that is not tied to one Docker host.

For example:

```text
SQLite -> external highly available database such as PostgreSQL

local named artifact volume -> shared/object storage such as S3-compatible storage
```

The main limitation is that the Compose stack coordinates containers on one Docker host but does not provide full multi-machine scheduling, high availability, or distributed persistent storage.

---

# Conclusion

Lab 4 extends the project from separately operated containers into a small multi-service application.

The architecture is:

```text
Human browser
     |
     v
Streamlit frontend
http://frontend:8501
     |
     | internal Compose network
     v
FastAPI inference
http://inference:8000
     |
     | internal Compose network
     v
MLflow
http://mlflow:5000
     |
     v
Named volume: mlflow-data
```

The responsibilities across the project are now:

```text
Git
-> source code and configuration

DVC
-> Food-11 dataset versions

MLflow Tracking
-> training experiments and metrics

MLflow Model Registry
-> registered model versions and deployment aliases

Docker
-> individual service images

Docker Compose
-> multi-container networking, configuration, startup order, and persistent volume wiring
```

The `staging` alias allows the inference service to use a stable model reference while the registered model version behind it can be replaced without rebuilding the inference image.
