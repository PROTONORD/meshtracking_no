#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Starting Meshtracking All-in-One Container..."

# Verify directories exist and are writable
if [ ! -w /var/lib/postgresql/data ]; then
    echo "❌ PostgreSQL data directory not writable (uid=$(id -u), ownership=$(stat -c '%u:%g' /var/lib/postgresql/data))"
    exit 1
fi

# Generate mosquitto.conf from template with environment variables
if [ ! -f /etc/mosquitto/conf.d/default.conf ]; then
    echo "📝 Generating mosquitto configuration..."
    envsubst < /app/mosquitto.conf.template > /etc/mosquitto/conf.d/default.conf
    
    # Create mosquitto password file
    echo "🔐 Setting up MQTT authentication..."
    echo "${MQTT_USER}:${MQTT_PASS}" > /etc/mosquitto/passwd
    mosquitto_passwd -U /etc/mosquitto/passwd || echo "Warning: mosquitto_passwd failed, continuing..."
    chmod 600 /etc/mosquitto/passwd
fi

# Copy web interface to data directory (only if not exists or older than source)
if [ ! -f /data/index.html ] || [ /app/index.html -nt /data/index.html ]; then
    echo "🌐 Deploying web interface..."
    cp /app/index.html /data/
    echo "✅ Web interface deployed: $(stat -c%s /data/index.html) bytes"
else
    echo "✅ Web interface already up to date"
fi

# Initialize meshtasticd config if needed
if [ ! -f /var/lib/meshtasticd/config.yaml ]; then
    echo "📡 Setting up meshtasticd configuration..."
    cp /app/config/config.yaml /var/lib/meshtasticd/ 2>/dev/null || true
    cp /app/config/node_sources.json /var/lib/meshtasticd/ 2>/dev/null || true
fi

# Initialize PostgreSQL if not already done
if [ ! -s /var/lib/postgresql/data/PG_VERSION ]; then
    echo "📦 Initializing PostgreSQL database as meshtracking user..."
    /usr/lib/postgresql/17/bin/initdb -D /var/lib/postgresql/data --auth-local=trust --auth-host=md5
    
    # Start PostgreSQL temporarily to create database and user
    /usr/lib/postgresql/17/bin/pg_ctl -D /var/lib/postgresql/data -l /var/log/postgresql/postgresql.log start
    sleep 5
    
    # Create database and user with environment variables (as meshtracking superuser)
    createdb -U meshtracking ${DB_NAME}
    createuser -U meshtracking ${DB_USER}
    psql -U meshtracking -c "ALTER USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';"
    psql -U meshtracking -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"
    
    # Run database schema initialization
    if [ -f /app/init.sql/schema.sql ]; then
        echo "📊 Initializing database schema..."
        psql -U meshtracking -d ${DB_NAME} -f /app/init.sql/schema.sql
    fi
    
    # Stop PostgreSQL to let supervisor manage it
    /usr/lib/postgresql/17/bin/pg_ctl -D /var/lib/postgresql/data stop
    sleep 2
    echo "✅ PostgreSQL initialized"
else
    # Database exists - reconcile password with production.env to prevent authentication failures
    echo "🔐 Reconciling database password with production.env..."
    /usr/lib/postgresql/17/bin/pg_ctl -D /var/lib/postgresql/data -l /var/log/postgresql/postgresql.log start
    sleep 3
    
    # Update password (idempotent - safe to run every time)
    # This prevents authentication failures after rebuilds when production.env changes
    psql -U meshtracking -d postgres -c "ALTER USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';" 2>/dev/null || echo "⚠️ Password update skipped (may already be correct)"
    
    /usr/lib/postgresql/17/bin/pg_ctl -D /var/lib/postgresql/data stop
    sleep 2
    echo "✅ Database password reconciled"
fi

echo "🎯 Starting all services with Supervisor..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf