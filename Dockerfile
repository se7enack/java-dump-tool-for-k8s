FROM python:3.11-slim

ENV INSIDE_CONTAINER=1

WORKDIR /app

# System deps (needed for kubernetes exec + ssl)
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

EXPOSE 5001

CMD ["python", "app.py"]
