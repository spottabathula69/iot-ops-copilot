FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py .
COPY schema.sql .

# Expose Prometheus metrics port
EXPOSE 8000

# Default command (override in K8s deployment)
CMD ["python", "consumer_postgres.py"]
