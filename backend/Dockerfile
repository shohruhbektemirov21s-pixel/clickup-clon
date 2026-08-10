# syntax=docker/dockerfile:1
#
# ClickUp clone — Django 5.2 + DRF + Channels 4, served over ASGI by Daphne.
# Build context: ./backend  (see docker-compose.yml)
#
# Multi-stage: the builder carries the C/Rust toolchain and the headers that
# some dependencies need when no cp314 wheel is published yet; the runtime
# stage only carries the shared libraries those extensions link against.

# ---------------------------------------------------------------------------
# Stage 1 — builder: resolve and compile every dependency into /opt/venv
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Why each package is here (mapped to backend/requirements.txt):
#   build-essential ........ C compiler + make: cffi, ujson, msgpack,
#                            Twisted/zope.interface C accelerators, PyYAML(libyaml)
#   libpq-dev .............. psycopg2-binary ships a manylinux wheel with libpq
#                            statically linked; this is the fallback that lets it
#                            compile (pg_config) if that wheel is missing for 3.14
#   libjpeg62-turbo-dev .... pillow — JPEG codec headers
#   zlib1g-dev ............. pillow — PNG/zlib headers
#   libfreetype6-dev ....... pillow — ImageFont (avatar/initials rendering)
#   libffi-dev ............. cffi (-> cryptography, pyOpenSSL, service-identity)
#   libssl-dev ............. cryptography / pyOpenSSL OpenSSL bindings
#   rustc + cargo .......... Rust extensions: cryptography, nh3, rpds-py
#                            (jsonschema -> drf-spectacular)
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        libpq-dev \
        libjpeg62-turbo-dev \
        zlib1g-dev \
        libfreetype6-dev \
        libffi-dev \
        libssl-dev \
        rustc \
        cargo \
    && rm -rf /var/lib/apt/lists/*

# Networks that inspect TLS re-sign pypi.org with a private root, and pip then
# fails with CERTIFICATE_VERIFY_FAILED. Drop such roots into backend/ca/*.crt
# and they get trusted here. pip trusts certifi's bundle rather than the system
# store, so PIP_CERT/SSL_CERT_FILE redirect it. The directory ships empty, so
# this is a no-op on networks that do not intercept.
COPY ca/ /usr/local/share/ca-certificates/
RUN update-ca-certificates
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# A self-contained virtualenv so the runtime stage is a single COPY.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

# Requirements first: this (slow) layer is only rebuilt when requirements.txt
# changes, not on every source edit.
COPY requirements.txt ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt


# ---------------------------------------------------------------------------
# Stage 2 — runtime: slim image, non-root, Daphne/ASGI
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    PATH="/opt/venv/bin:${PATH}"

# Runtime shared libraries only (no headers, no compilers):
#   libpq5 ............ psycopg2 (PostgreSQL client library)
#   libjpeg62-turbo ... pillow JPEG
#   zlib1g ............ pillow PNG/zlib
#   libfreetype6 ...... pillow ImageFont
#   curl .............. not installed on purpose — HEALTHCHECK uses python stdlib
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libpq5 \
        libjpeg62-turbo \
        zlib1g \
        libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

# Never run as root.
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Application source (paths relative to the ./backend build context):
#   manage.py, config/, apps/, conftest.py, pytest.ini, requirements.txt
COPY --chown=appuser:appuser . .

# Entrypoint on PATH. The sed strips CRLF line endings so the script still
# works when the repo was checked out on Windows.
COPY --chown=appuser:appuser docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

# STATIC_ROOT = BASE_DIR/staticfiles, MEDIA_ROOT = BASE_DIR/media (settings.py).
# Creating + chowning them here means the named volumes mounted on these paths
# inherit appuser ownership on first use.
RUN mkdir -p /app/staticfiles /app/media

# WhiteNoise uses CompressedManifestStaticFilesStorage, which needs the manifest
# to exist before the first request — so collect at build time.
#
# DEBUG=True is required *for this RUN only*: with DEBUG off, settings.py
# rejects a missing/weak SECRET_KEY and an empty ALLOWED_HOSTS at import time,
# and collectstatic would abort. The throwaway key below never leaves this
# layer — the running container gets its real SECRET_KEY from the environment.
# (.dockerignore also keeps the host .env out of the build context.)
RUN DEBUG=True \
    SECRET_KEY=build-stage-placeholder-not-used-at-runtime-0000000000000000 \
    ALLOWED_HOSTS=localhost,127.0.0.1 \
    python manage.py collectstatic --noinput --clear \
    && chown -R appuser:appuser /app/staticfiles /app/media

USER appuser

EXPOSE 8000

# /api/v1/health/ is AllowAny (config/urls.py). urllib keeps the image curl-free.
#
# X-Forwarded-Proto: https is deliberate. With DEBUG=False settings.py turns on
# SECURE_SSL_REDIRECT together with SECURE_PROXY_SSL_HEADER, so a plain http
# probe would get a 301 to https and the container would never report healthy.
# In dev (DEBUG=True) neither setting is active and the header is ignored.
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request as u; req = u.Request('http://127.0.0.1:8000/api/v1/health/', headers={'X-Forwarded-Proto': 'https'}); sys.exit(0 if u.urlopen(req, timeout=5).status == 200 else 1)"]

ENTRYPOINT ["docker-entrypoint.sh"]

# ASGI, not WSGI and not runserver: Channels/WebSocket traffic needs Daphne.
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
