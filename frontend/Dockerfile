# syntax=docker/dockerfile:1
#
# ClickUp clone — Next.js 16 (App Router) frontend.
# Build context: ./frontend  (see docker-compose.yml)
#
# Relies on `output: "standalone"` in next.config.ts, which emits
# .next/standalone/server.js plus only the node_modules it actually traces.

FROM node:22-alpine AS base
# Next.js' prebuilt native binaries are glibc-linked; libc6-compat provides the
# shim Alpine needs to load them.
RUN apk add --no-cache libc6-compat


# ---------------------------------------------------------------------------
# Stage 1 — deps: install node_modules from the lockfile only
# ---------------------------------------------------------------------------
FROM base AS deps
WORKDIR /app

# Cached until package.json / package-lock.json change.
COPY package.json package-lock.json ./
RUN npm ci


# ---------------------------------------------------------------------------
# Stage 2 — builder: next build
# ---------------------------------------------------------------------------
FROM base AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
# .dockerignore keeps host node_modules/ and .next/ out of the context, so this
# does not clobber the layer above.
COPY . .

# NEXT_PUBLIC_* is inlined into the client bundle at BUILD time — it cannot be
# supplied later via `docker run -e`. Values mirror frontend/src/lib/env.ts.
ARG NEXT_PUBLIC_API_BASE_URL="http://localhost:8000/api/v1"
ARG NEXT_PUBLIC_WS_BASE_URL="ws://localhost:8000"
ARG NEXT_PUBLIC_API_MODE="real"

ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} \
    NEXT_PUBLIC_WS_BASE_URL=${NEXT_PUBLIC_WS_BASE_URL} \
    NEXT_PUBLIC_API_MODE=${NEXT_PUBLIC_API_MODE} \
    NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

RUN npm run build


# ---------------------------------------------------------------------------
# Stage 3 — runner: minimal standalone server, non-root
# ---------------------------------------------------------------------------
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# The standalone server does NOT bundle public/ or .next/static — copy them in.
COPY --from=builder --chown=node:node /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

# node:22-alpine ships an unprivileged `node` user (uid 1000).
USER node

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
