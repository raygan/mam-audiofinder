FROM python:3.12-slim

# Accept build arguments for user/group IDs (defaults match common Docker user IDs)
ARG PUID=1000
ARG PGID=1000

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Create a user and group with specified PUID/PGID
RUN groupadd -g ${PGID} appuser && \
    useradd -u ${PUID} -g ${PGID} -m -s /bin/bash appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/
COPY validate_env.py /app/

# Ensure the app directory and files are owned by appuser
RUN chown -R ${PUID}:${PGID} /app

EXPOSE 8080

# Note: docker-compose.yml overrides this with user: "${PUID}:${PGID}"
# but we set a default user here for when running without compose
USER ${PUID}:${PGID}

CMD ["sh", "-c", "python validate_env.py && uvicorn main:app --host 0.0.0.0 --port 8080"]
