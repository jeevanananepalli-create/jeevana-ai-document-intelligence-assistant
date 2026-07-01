# Backend container image.
#
# Multi-stage build:
#   - "builder" installs Python dependencies into an isolated virtualenv.
#   - the final stage copies only that virtualenv and the app code, producing a
#     smaller image that contains no build tools.
#
# Why containerise at all: the image bundles the exact Python version and the
# exact dependency versions, so the app runs identically on every developer's
# machine and in CI/production. No more "works on my machine".

# ---- Stage 1: build dependencies -----------------------------------------
FROM python:3.12-slim AS builder

# Don't write .pyc files; stream stdout/stderr straight to the terminal.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# psycopg2 (the sync driver Alembic uses) needs a C toolchain to build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a dedicated virtualenv we can copy wholesale into the runtime image.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install the project into the venv. The heavy embedding stack (torch) is opt-in
# via the INSTALL_ML build arg, so the API image stays light and only the worker
# image pulls it in.
ARG INSTALL_ML=false
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --upgrade pip \
    && if [ "$INSTALL_ML" = "true" ]; then pip install ".[ml]"; else pip install "."; fi

# ---- Stage 2: runtime -----------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Runtime system libraries:
#   libpq5         - what psycopg2 links against (database driver)
#   tesseract-ocr  - the OCR engine used by pytesseract (image / scanned-PDF text)
#   poppler-utils  - PDF rendering used by pdf2image (scanned-PDF -> images)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        tesseract-ocr \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy the ready-built virtualenv from the builder stage.
COPY --from=builder /opt/venv /opt/venv

# Copy the application source and migration tooling.
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./

# Run as a non-root user — a basic, important security hardening step so a
# compromised process does not have root inside the container.
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000

# Default command. docker-compose overrides this in development to add --reload.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
