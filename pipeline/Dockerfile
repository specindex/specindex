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
# OFFICIAL PLAYWRIGHT IMAGE, not python:3.12-slim.
#
# The first build failed exactly where pipeline/README.md predicted:
# `playwright install --with-deps chromium` on slim tries to apt-get
# `ttf-unifont` and `ttf-ubuntu-font-family`, which Debian trixie renamed to
# `fonts-unifont` -- "has no installation candidate", exit 100.
#
# Chasing renamed Debian font packages is a maintenance treadmill that breaks
# again on the next base bump. Microsoft's image ships Chromium and every system
# dependency already matched to the Playwright version, so there is nothing to
# keep in sync.
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pipeline/requirements.txt .
# Browsers are already present in this image; only the Python deps are needed.
RUN pip install --no-cache-dir -r requirements.txt

# Code and source tables only. Documents live in GCS, never in the image.
COPY scripts/  ./scripts/
COPY config/   ./config/
COPY coverage/data/ ./coverage/data/
COPY db/       ./db/

# No ENTRYPOINT command baked in: one image, many jobs. Cloud Run Jobs supplies
# the args, so a new job is a deploy flag rather than a new image.
ENTRYPOINT ["python3"]
CMD ["--version"]
