FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# 1) System deps needed to build native wheels like psutil
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential python3-dev \
 && rm -rf /var/lib/apt/lists/*

# 2) Python deps
COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir --prefer-binary -r requirements.txt

# 3) Your app
COPY agent.py .
CMD ["python", "agent.py"]
