# syntax=docker/dockerfile:1.7
#
# Streamlit app (Python + uv).

FROM python:3.13-slim AS deps
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM python:3.13-slim AS runtime
WORKDIR /app

# --home:--system 預設家目錄為 /nonexistent(不可寫),Streamlit 寫 ~/.streamlit
#        會 PermissionError,NewSession 送不出 → 前端 session 建不起來、無法上傳
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup --home /home/appuser appuser

COPY --from=deps /app/.venv /app/.venv
COPY --chown=appuser:appgroup . .

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8501

CMD ["streamlit", "run", "app.py", \
     "--server.address", "0.0.0.0", \
     "--server.port", "8501", \
     "--server.headless", "true"]
