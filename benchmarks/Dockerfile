FROM python:3.12-slim
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONUNBUFFERED=1 HF_HUB_DISABLE_TELEMETRY=1 TOKENIZERS_PARALLELISM=false
WORKDIR /work
COPY benchmarks/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt
ENTRYPOINT ["python", "benchmarks/compare_models.py"]
