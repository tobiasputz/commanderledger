FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    COMMANDER_MODE=hosted COMMANDER_DB=/data/commander.db \
    COMMANDER_BACKUPS=/data/backups COMMANDER_REQUIRE_MOUNT=true
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "-m", "app.hosted"]
