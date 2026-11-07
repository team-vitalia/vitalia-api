FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# requirements.txt viene con BOM (UTF-8) desde Windows; lo limpiamos por seguridad
COPY requirements.txt .
RUN sed -i '1s/^\xEF\xBB\xBF//' requirements.txt \
    && pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]