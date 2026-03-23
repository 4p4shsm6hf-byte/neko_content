FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create runtime directories (also created by main.py, but explicit is better)
RUN mkdir -p media_cache logs

CMD ["python", "main.py"]
