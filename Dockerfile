FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Run with gunicorn
# Ensure SCRIPT_NAME is unset in the OS environment so Gunicorn's internal parser
# doesn't reject incoming requests whose prefix was already stripped by Traefik.
CMD ["sh", "-c", "export APPLICATION_ROOT=${APPLICATION_ROOT:-$SCRIPT_NAME}; unset SCRIPT_NAME; exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:application"]
