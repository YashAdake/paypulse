# Stage 1: build the static site. Node exists only in this stage, never at runtime.
FROM node:24.22.1-alpine AS build
WORKDIR /app
# Direct dependencies are pinned in package.json. No lockfile yet: it is generated on the
# first build here, since Node is not run on the dev laptop.
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
# Type-checks first: a type error fails the build instead of shipping a broken UI.
RUN npm run build

# Stage 2: tiny non-root nginx serving the files and proxying /api to the api service.
FROM nginxinc/nginx-unprivileged:1.31.7-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
