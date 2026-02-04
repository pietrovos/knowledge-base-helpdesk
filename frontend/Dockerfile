# Production web image: static build served by unprivileged nginx.
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY security-headers.conf /etc/nginx/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
# In AWS the load balancer routes /api to the API service; for a single-host deployment set
# API_UPSTREAM (e.g. http://api:8000) and nginx proxies /api itself.
ENV API_UPSTREAM=http://api:8000
EXPOSE 8080
