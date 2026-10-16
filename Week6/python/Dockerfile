FROM python:3.12-slim AS dependencies
WORKDIR /build
COPY requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --system --uid 10001 --create-home appuser
COPY --from=dependencies /install /usr/local
COPY --chown=appuser:appuser app.py ./
USER appuser
EXPOSE 5000
CMD ["python", "app.py"]
