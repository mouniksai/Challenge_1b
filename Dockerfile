# Multi-stage build for optimized CPU-only document analysis
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir --user -r /tmp/requirements.txt

# Final stage - minimal runtime image
FROM python:3.11-slim

# Install runtime dependencies for llama-cpp-python
RUN apt-get update && apt-get install -y \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Set environment variables for CPU-only processing
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV OMP_NUM_THREADS=4
ENV LLAMA_CPP_THREADS=4

# Create application user for security first
RUN useradd --create-home --shell /bin/bash app && \
    mkdir -p /app/output /app/models /app/PDFs && \
    chown -R app:app /app

# Copy Python packages from builder and set correct ownership
COPY --from=builder /root/.local /home/app/.local
RUN chown -R app:app /home/app/.local

# Copy application files
COPY --chown=app:app main.py .
COPY --chown=app:app input/1binput.json .

# Copy PDFs directory (if exists)
COPY --chown=app:app PDFs/ ./PDFs/

# Copy the model file (874MB - under 1GB constraint)
COPY --chown=app:app models/gemma-3-1b-it-UD-Q5_K_XL.gguf models/

# Switch to application user
USER app

# Health check to ensure the application can start
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import llama_cpp, fitz; print('Dependencies OK')" || exit 1

# Set the PATH to include user packages  
ENV PATH=/home/app/.local/bin:$PATH

# Default command - runs the optimized document analysis
CMD ["python", "main.py"]
