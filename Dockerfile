FROM python:3.12-slim

WORKDIR /app

# Install system dependencies: LibreOffice for DOCX/XLSX→PDF, poppler for PDF→PNG
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies and audit for known CVEs
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pip-audit \
    && pip-audit -r requirements.txt \
    && pip uninstall -y pip-audit 2>/dev/null || true

# Copy application code
COPY . .

# Create necessary directories and a non-root user
RUN mkdir -p temp_uploads generated_documents static && useradd --create-home --shell /bin/bash app && chown -R app:app /app

USER app

# Expose the port Railway will assign
EXPOSE 8000

# Run the combined entry point
CMD ["python", "run.py"]
