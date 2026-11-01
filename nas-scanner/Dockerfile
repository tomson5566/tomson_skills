# ---------- 构建阶段 ----------
FROM node:20-alpine AS builder
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@latest --activate

# 先装依赖，充分利用镜像层缓存
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm run build

# ---------- 运行阶段 ----------
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    COZE_PROJECT_ENV=PROD \
    PORT=5000 \
    HOSTNAME=0.0.0.0

COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/public ./public

EXPOSE 5000
CMD ["node", "dist/server.js"]
