
FROM python:3.11-slim-bookworm
WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential python3-dev git libffi-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY . .
CMD ["python", "agent.py"]
