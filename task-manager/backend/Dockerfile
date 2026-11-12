FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY . /src
RUN set -e; \
    M=$(find /src -name manage.py -not -path "*/node_modules/*" -not -path "*/venv/*" | head -1); \
    if [ -z "$M" ]; then echo "manage.py NOT FOUND. Folder tree:"; find /src -maxdepth 3; exit 1; fi; \
    echo "Using project folder: $(dirname "$M")"; \
    cp -r "$(dirname "$M")"/. /app/; \
    rm -rf /src; \
    pip install --no-cache-dir -r requirements.txt
RUN SECRET_KEY=build USE_SQLITE=True python manage.py collectstatic --noinput
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2"]
