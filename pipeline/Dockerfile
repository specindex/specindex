# Pipeline container for Cloud Run Jobs.
#
# WHY THIS EXISTS. api/Dockerfile packages main.py only -- it cannot run an
# adapter. Long jobs have been running on Asif's laptop, and pmset shows exactly
# why that fails: repeated "Maintenance Sleep" and "Dark Wake Thermal Emergency"
# through the window where four separate jobs died with "server closed the
# connection unexpectedly". Cloud SQL was fine throughout (12 of 400 connections,
# 0.4s response); the machine was asleep. The build brief is right that nothing
# should run on the laptop.
#
# Playwright is included because several verified adapters need a real browser:
# North Carolina's eVP is a Power Pages app that returns zero solicitation ids to
# a plain fetch, and Arkansas 403s everything except headless Chromium with its
# OWN user agent left alone.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pipeline/requirements.txt .
RUN pip install -r requirements.txt \
    && python -m playwright install --with-deps chromium

# Code and source tables only. Documents live in GCS, never in the image.
COPY scripts/  ./scripts/
COPY config/   ./config/
COPY coverage/data/ ./coverage/data/
COPY db/       ./db/

# No ENTRYPOINT command baked in: one image, many jobs. Cloud Run Jobs supplies
# the args, so a new job is a deploy flag rather than a new image.
ENTRYPOINT ["python3"]
CMD ["--version"]
