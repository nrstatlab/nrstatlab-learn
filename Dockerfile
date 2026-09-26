FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# The content submodule must be checked out in the build context (git clone --recurse-submodules).
RUN DJANGO_SETTINGS_MODULE=config.settings.prod SECRET_KEY=build-only DATABASE_URL=sqlite:////tmp/build.db \
    python manage.py import_site --files-only && \
    DJANGO_SETTINGS_MODULE=config.settings.prod SECRET_KEY=build-only DATABASE_URL=sqlite:////tmp/build.db \
    python manage.py collectstatic --noinput
EXPOSE 8000
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "30"]
