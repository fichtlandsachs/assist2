# Stage 1: base
FROM node:24-alpine AS base
WORKDIR /app

# Stage 2: builder
FROM base AS builder
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_APP_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN mkdir -p /app/public
RUN npm run build

# Stage 3: production
FROM node:24-alpine AS production
WORKDIR /app

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 appuser

COPY --from=builder --chown=appuser:nodejs /app/.next ./.next
COPY --from=builder --chown=appuser:nodejs /app/node_modules ./node_modules
RUN mkdir -p ./public
COPY --chown=appuser:nodejs public/ ./public/
COPY --chown=appuser:nodejs package.json ./

USER appuser

EXPOSE 3000

ENV NODE_ENV=production
ENV PORT=3000

CMD ["npm", "start"]
