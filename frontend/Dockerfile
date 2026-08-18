# LandVISION 前端镜像 —— 多阶段构建（产物小：node 构建 → nginx 托管）
# 阶段一：构建
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install --registry=https://registry.npmmirror.com
COPY . .
RUN npm run build

# 阶段二：运行（只保留 dist 产物）
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
