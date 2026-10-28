FROM python:3.11-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    XDG_CACHE_HOME=/tmp/cache \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1
COPY service/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir -r /tmp/requirements.txt
COPY service/ ./service/
COPY ml/src/ ./ml/src/
COPY ml/frozen_ppo_manifest.json ml/third-party-notices.txt ./ml/
COPY simulation/ ./simulation/
COPY data/ ./data/
COPY artifacts/frozen/public-data-v2/ ./artifacts/frozen/public-data-v2/
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
