# LandVISION 后端镜像（生产部署用，见 deploy/docker-compose.yml）
FROM python:3.12-slim

WORKDIR /app

# 安装依赖（利用 Docker 层缓存：requirements 不变则不再重复安装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app ./app
COPY run.py .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
