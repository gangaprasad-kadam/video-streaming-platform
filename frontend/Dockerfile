# ─────────────────────────────────────────
# Stage 1 — Build
# ─────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY . .
RUN npm run build          # outputs to /app/dist

# ─────────────────────────────────────────
# Stage 2 — Serve (lightweight nginx)
# ─────────────────────────────────────────
FROM nginx:alpine

# Install envsubst (part of gettext) for runtime env-var substitution
RUN apk add --no-cache gettext

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# BACKEND_URL is substituted at container start via envsubst
# Default: http://host.docker.internal:80 (backend on same host)
ENV BACKEND_URL=http://host.docker.internal:80

EXPOSE 80

# nginx official image auto-processes /etc/nginx/templates/*.template via envsubst
CMD ["nginx", "-g", "daemon off;"]
