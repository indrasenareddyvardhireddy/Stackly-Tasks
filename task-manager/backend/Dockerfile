FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential pkg-config default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# collect admin static files at build time (no database needed)
RUN SECRET_KEY=build USE_SQLITE=True python manage.py collectstatic --noinput
EXPOSE 8000
# Once you commit the generated migrations you can drop the makemigrations step.
CMD ["sh", "-c", "python manage.py makemigrations accounts tasks && python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2"]
