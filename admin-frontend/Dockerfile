FROM node:24-alpine AS base
WORKDIR /app

FROM base AS builder
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_AUTHENTIK_URL
ARG NEXT_PUBLIC_ADMIN_CLIENT_ID
ARG NEXT_PUBLIC_ADMIN_REDIRECT_URI
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_AUTHENTIK_URL=$NEXT_PUBLIC_AUTHENTIK_URL
ENV NEXT_PUBLIC_ADMIN_CLIENT_ID=$NEXT_PUBLIC_ADMIN_CLIENT_ID
ENV NEXT_PUBLIC_ADMIN_REDIRECT_URI=$NEXT_PUBLIC_ADMIN_REDIRECT_URI
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:24-alpine AS production
WORKDIR /app
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 appuser
COPY --from=builder --chown=appuser:nodejs /app/.next/standalone ./
COPY --from=builder --chown=appuser:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=appuser:nodejs /app/public ./public
USER appuser
EXPOSE 3001
ENV NODE_ENV=production PORT=3001 HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
