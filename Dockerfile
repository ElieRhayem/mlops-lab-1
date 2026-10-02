# syntax=docker/dockerfile:1

# ---------------------------------------------------------
# Stage 1: Builder
# ---------------------------------------------------------

FROM python:3.13 AS builder

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies, but don't install the project itself
RUN uv sync --frozen --no-dev --no-install-project


# ---------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------

FROM python:3.13-slim AS runtime

WORKDIR /app

# Copy only the ready virtual environment from the builder.
COPY --from=builder /app/.venv /app/.venv

# Copy application source code.
COPY src ./src

# Make executables from the virtual environment available.
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn","src.food11.serve:app","--host","0.0.0.0","--port","8000"]