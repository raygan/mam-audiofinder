# ============================================================================
# Stage 1: Production Image (Lean, Production-Ready)
# ============================================================================
FROM python:3.12-slim AS production

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

# ============================================================================
# Stage 2: Testing Image (Includes Test Dependencies + Selenium Browser)
# ============================================================================
FROM production AS testing

# Switch back to root to install test dependencies
USER root

# Install system dependencies for testing
# - make: For Makefile test targets
# - chromium & chromium-driver: For Selenium browser testing
# - fonts & locales: For proper rendering in headless browser
RUN apt-get update && apt-get install -y --no-install-recommends \
    make \
    chromium \
    chromium-driver \
    fonts-liberation \
    libnss3 \
    libxss1 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python test dependencies
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy test suite
COPY app/tests/ /app/tests/
COPY Makefile /app/

# Set environment variables for Selenium to use local Chrome
ENV SELENIUM_DRIVER_TYPE=local \
    SELENIUM_BROWSER=chrome \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Create test data directory (in-memory tests will use /tmp, integration tests can use /data)
RUN mkdir -p /data/test-data && \
    chown -R ${PUID}:${PGID} /app /data/test-data

# Switch back to app user
USER ${PUID}:${PGID}

# Default: Run full test suite
CMD ["pytest", "tests/", "-v", "--tb=short"]
