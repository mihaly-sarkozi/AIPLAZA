FROM node:20-alpine

WORKDIR /app/frontend

RUN corepack enable && corepack prepare pnpm@10.17.1 --activate

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend ./
COPY backend/apps /app/backend/apps

EXPOSE 5173

CMD ["sh", "-c", "pnpm dev --host 0.0.0.0 --port 5173"]
