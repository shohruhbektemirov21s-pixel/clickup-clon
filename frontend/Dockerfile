# syntax=docker/dockerfile:1
#
# UzWork frontend — React 19 + Vite SPA (ADR 0011).
# Build context: ./frontend  (see docker-compose.yml)
#
# Chiqish — statik `dist/`; uni nginx tarqatadi. Ilgari bu image Next'ning
# `output: "standalone"` server.js ini ishga tushirardi; SPA'da Node runtime
# umuman kerak emas.

# Debian-slim, not Alpine: prebuilt native binaries in the toolchain are
# glibc-linked, so glibc images need no shim package at all. Alpine would need
# libc6-compat, and installing it fails outright on networks that MITM TLS to
# the apk CDN.
FROM node:22-slim AS base

# Networks that inspect TLS re-sign registry.npmjs.org with a private root, and
# npm then fails with UNABLE_TO_VERIFY_LEAF_SIGNATURE. Drop such roots into
# frontend/ca/*.crt and they get trusted here. The directory ships empty, so
# this is a no-op on networks that do not intercept.

# node:22-slim ships no CA store at all — Node uses its compiled-in bundle, so
# there is nothing for a private root to be added to. Install one first; the
# Debian archive is fetched over plain HTTP with GPG-signed indexes, so this
# step works even on a network whose TLS is being intercepted.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY ca/ /usr/local/share/ca-certificates/
RUN update-ca-certificates \
    && printf 'cafile=/etc/ssl/certs/ca-certificates.crt\n' >> /usr/local/etc/npmrc
ENV NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt


# ---------------------------------------------------------------------------
# Stage 1 — deps: install node_modules from the lockfile only
# ---------------------------------------------------------------------------
FROM base AS deps
WORKDIR /app

# Cached until package.json / package-lock.json change.
COPY package.json package-lock.json ./
RUN npm ci


# ---------------------------------------------------------------------------
# Stage 2 — builder: vite build → /app/dist
# ---------------------------------------------------------------------------
FROM base AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
# .dockerignore keeps host node_modules/ and dist/ out of the context, so this
# does not clobber the layer above.
COPY . .

# VITE_* is inlined into the client bundle at BUILD time — it cannot be
# supplied later via `docker run -e`. Values mirror frontend/src/lib/env.ts.
ARG VITE_API_BASE_URL="http://localhost:8000/api/v1"
ARG VITE_WS_BASE_URL="ws://localhost:8000"
ARG VITE_API_MODE="real"

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_WS_BASE_URL=${VITE_WS_BASE_URL} \
    VITE_API_MODE=${VITE_API_MODE} \
    NODE_ENV=production

RUN npm run build


# ---------------------------------------------------------------------------
# Stage 3 — runner: nginx serves the static build, non-root
# ---------------------------------------------------------------------------
#
# `nginxinc/nginx-unprivileged` — rasmiy nginx image'ining root'siz varianti
# (uid 101). 3000 > 1024, shuning uchun imtiyozsiz jarayon uni bemalol
# tinglaydi.
FROM nginxinc/nginx-unprivileged:1.29-alpine AS runner

# CSP'dagi origin'lar bundle ichidagi manzillar bilan bir xil bo'lishi kerak,
# ya'ni ular ham build vaqtida aniqlanadi.
ARG VITE_API_BASE_URL="http://localhost:8000/api/v1"
ARG VITE_WS_BASE_URL="ws://localhost:8000"

USER root

COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template

# Manzildan faqat `scheme://host[:port]` qismi olinadi — CSP manba sifatida
# yo'l (`/api/v1`) qabul qilinmaydi.
RUN set -eu; \
    origin_of() { printf '%s' "$1" | sed -E 's#^([a-zA-Z][a-zA-Z0-9+.-]*://[^/]+).*#\1#'; }; \
    api_origin="$(origin_of "$VITE_API_BASE_URL")"; \
    ws_origin="$(origin_of "$VITE_WS_BASE_URL")"; \
    sed -e "s|\${API_ORIGIN}|${api_origin}|g" -e "s|\${WS_ORIGIN}|${ws_origin}|g" \
        /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf; \
    rm -f /etc/nginx/templates/default.conf.template

COPY --from=builder --chown=101:101 /app/dist /usr/share/nginx/html

USER 101

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:3000/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
