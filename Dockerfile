FROM python:3.12-slim

# Create non-root user matching host user (meshtracking with uid 1001)
RUN groupadd -g 1001 meshtracking && \
    useradd -u 1001 -g 1001 -m -s /bin/bash meshtracking

# Install system dependencies including PostgreSQL, Mosquitto
RUN apt-get update && apt-get install -y \
    postgresql postgresql-contrib postgresql-client \
    mosquitto mosquitto-clients \
    nmap gcc python3-dev supervisor \
    curl wget procps gettext-base \
    libusb-1.0-0 libuv1 sudo \
    && rm -rf /var/lib/apt/lists/*

# Add meshtracking to necessary groups
RUN usermod -a -G dialout,postgres,mosquitto meshtracking && \
    echo "meshtracking ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers# Install Python dependencies
RUN pip install --no-cache-dir \
    meshtastic==2.7.3 \
    paho-mqtt==1.6.1 \
    pypubsub==4.0.3 \
    psycopg2-binary==2.9.9 \
    flask==3.0.0 \
    flask-cors==4.0.0 \
    pytz==2024.1 \
    netifaces==0.11.0 \
    pycryptodome==3.20.0

# Setup PostgreSQL user and directory permissions
RUN usermod -d /var/lib/postgresql postgres && \
    mkdir -p /var/lib/postgresql && \
    chown -R postgres:postgres /var/lib/postgresql && \
    chmod 755 /var/lib/postgresql

# Create mosquitto directories (user already exists from mosquitto package)
RUN mkdir -p /var/lib/mosquitto /var/log/mosquitto /etc/mosquitto/conf.d && \
    chown -R mosquitto:mosquitto /var/lib/mosquitto /var/log/mosquitto && \
    chmod 755 /var/lib/mosquitto /var/log/mosquitto

# Create app directory and copy application files
WORKDIR /app
COPY --chown=meshtracking:meshtracking *.py *.sh *.sql *.html ./
COPY --chown=meshtracking:meshtracking init.sql/ ./init.sql/
COPY --chown=meshtracking:meshtracking config/ ./config/

# Copy supervisor and mosquitto configurations
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY mosquitto.conf.template /app/mosquitto.conf.template

# Create all required directories and set proper ownership during build (as root)
RUN mkdir -p /data /var/lib/postgresql/data /var/log/supervisor /var/lib/meshtasticd \
              /var/log/postgresql /run/postgresql /var/lib/mosquitto /var/log/mosquitto \
              /etc/mosquitto/conf.d && \
    chown -R meshtracking:meshtracking /data /var/lib/postgresql /var/log/supervisor /var/lib/meshtasticd \
                           /var/log/postgresql /run/postgresql /var/lib/mosquitto \
                           /var/log/mosquitto /app /etc/mosquitto && \
    chmod +x /app/*.sh && \
    chmod 755 /app/start-all.sh && \
    cp /app/index.html /data/index.html && \
    chown meshtracking:meshtracking /data/index.html

# Switch to non-root user for better security
USER meshtracking

# Expose ports (8088=web, 1883=MQTT, 5432=PostgreSQL, 4403=meshtasticd TCP, 9443=meshtasticd web)
EXPOSE 8088 1883 5432 4403 9443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
  CMD curl -f http://localhost:8088/api/health || exit 1

# Start all services via startup script
CMD ["/app/start-all.sh"]
