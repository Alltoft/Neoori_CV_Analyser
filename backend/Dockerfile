# Base image from AWS's public mirror of Docker's official images (same
# digests as Docker Hub): Docker Hub rate-limits GitHub's shared CI runners
# (429 Too Many Requests on every deploy attempt, 2026-10-09).
FROM public.ecr.aws/docker/library/python:3.14-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_APP=run.py

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh

EXPOSE 5000

# Production: wait for DB -> migrate -> gunicorn. The dev compose overrides
# this with `command: flask run --debug` so local development is unchanged.
CMD ["/app/entrypoint.sh"]
