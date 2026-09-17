FROM python:3.11-slim

LABEL com.ml-autoscaler.project="cloud-resource-autoscaling" \
      com.ml-autoscaler.role="application" \
      com.ml-autoscaler.managed="true"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --home /app appuser

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
