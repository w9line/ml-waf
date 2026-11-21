FROM python:3.12-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends nftables iproute2 curl openssh-server openssl nginx procps && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/aegis/app
COPY pyproject.toml ./
COPY aegis ./aegis
RUN python -m pip install --no-cache-dir ".[ml]" Flask FastAPI uvicorn
COPY lab /opt/aegis/lab
RUN cp /opt/aegis/lab/nginx.conf /etc/nginx/nginx.conf
COPY emergency-stop.sh /opt/aegis/app/emergency-stop.sh
