FROM node:20-bookworm-slim AS deps
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci

FROM node:20-bookworm-slim AS builder
WORKDIR /app/frontend
COPY --from=deps /app/frontend/node_modules ./node_modules
COPY frontend ./
RUN npm run build

FROM node:20-bookworm-slim AS runner
WORKDIR /app/frontend

ENV NODE_ENV=production

COPY --from=builder /app/frontend/.next ./.next
COPY --from=builder /app/frontend/public ./public
COPY --from=builder /app/frontend/package*.json ./
COPY --from=deps /app/frontend/node_modules ./node_modules

EXPOSE 3000

CMD ["npm", "run", "start:lan"]
