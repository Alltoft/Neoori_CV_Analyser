FROM python:3.14-slim

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
