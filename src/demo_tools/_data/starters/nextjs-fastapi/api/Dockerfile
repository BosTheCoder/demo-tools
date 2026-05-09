FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . ./
RUN mkdir -p /data
EXPOSE 8000
# Bind dual-stack: Fly's .internal private network is IPv6-only, so the
# web app reaches us via IPv6. On Linux, IPv6 sockets accept IPv4 too
# (IPV6_V6ONLY=0), so :: covers both 6PN and 127.0.0.1.
CMD ["uvicorn", "main:app", "--host", "::", "--port", "8000"]
