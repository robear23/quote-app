FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p temp_uploads generated_documents static

# Expose the port Railway will assign
EXPOSE 8000

# Run the combined entry point
CMD ["python", "run.py"]
