FROM python:3.11-slim

WORKDIR /app

# Ensure logs appear in real-time in Dokploy console
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source files
COPY . .

# Launch Agri Solutions Group Discord Bot
CMD ["python", "main.py"]
