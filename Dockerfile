FROM python:3.10-slim

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Copy application code
COPY app/ ./app/
COPY pipeline/ ./pipeline/

# Create necessary directories
RUN mkdir -p /app/data /app/logs

# Expose port
EXPOSE 8000

# Run the application (Render uses PORT env variable)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
