# Base images from AWS's public mirror of Docker's official images (same
# digests as Docker Hub): Docker Hub rate-limits GitHub's shared CI runners
# (429 Too Many Requests on every deploy attempt, 2026-10-09).
# ---- deps: install exact lockfile deps ----
FROM public.ecr.aws/docker/library/node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- builder: next build (standalone output, see next.config.ts) ----
FROM public.ecr.aws/docker/library/node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# No site URL is baked in: the frontend reads DOMAIN at request time
# (subdomain split spec, decision 21).
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---- runner: minimal standalone server, no node_modules ----
FROM public.ecr.aws/docker/library/node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    NEXT_TELEMETRY_DISABLED=1

RUN addgroup -S nodejs -g 1001 && adduser -S nextjs -u 1001 -G nodejs

# server.js does not bundle public/ or .next/static — copy them in so the
# standalone server serves them itself (nginx sits in front regardless).
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
