# World Brief: daily world-news email + podcast. Runs forever and sends on time.
#   docker compose up -d        (see README)
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg git ca-certificates fonts-dejavu-core tzdata \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/world-brief
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY feeds feeds
COPY examples examples
COPY config.example.yaml setup.py ./

# Non-root; only /data is writable (config.yaml, .env, state, briefs, logs live there).
RUN useradd --create-home --uid 10001 wb && mkdir -p /data && chown wb:wb /data
USER wb
ENV WB_DATA=/data PYTHONUNBUFFERED=1
VOLUME ["/data"]

ENTRYPOINT ["python", "-m", "app"]
CMD ["serve"]
