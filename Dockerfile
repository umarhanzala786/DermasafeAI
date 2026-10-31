FROM python:3.11-slim

WORKDIR /app

# System dependencies for TensorFlow
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Create upload directories
RUN mkdir -p uploads static/uploads

EXPOSE 5000

ENV FLASK_ENV=production

CMD ["python", "app.py"]

