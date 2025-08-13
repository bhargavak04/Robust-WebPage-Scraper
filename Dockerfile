# Use the official Playwright image which comes with browsers and dependencies installed
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
# The base image runs as root, so we allow it here.
# The user will be switched later.
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# The base image has a 'pwuser'. We'll use that user.
# Give ownership of the app directory to the pwuser
USER root
RUN chown -R pwuser:pwuser /app
USER pwuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "main.py"]
