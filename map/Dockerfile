FROM python:3.12-slim

# Install build dependencies, PostgreSQL client and nmap for device discovery
RUN apt-get update && \
    apt-get install -y \
    postgresql-client \
    nmap \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    meshtastic==2.7.3 \
    paho-mqtt==1.6.1 \
    pypubsub==4.0.3 \
    psycopg2-binary==2.9.9 \
    flask==3.0.0 \
    flask-cors==4.0.0 \
    netifaces==0.11.0

WORKDIR /app
COPY index.html mqtt_collector_pg.py node_poller.py node_api.py combined_server.py db_to_geojson_pg.py device_manager.py cleanup_old_nodes.py scan_network.sh run.sh AGENTS.md ./

ENTRYPOINT ["/app/run.sh"]
