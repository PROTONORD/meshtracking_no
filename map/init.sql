-- Meshtastic PostgreSQL Schema
-- Designed for high-concurrency multi-source data collection

CREATE TABLE IF NOT EXISTS nodes (
    node_id TEXT PRIMARY KEY,
    node_num BIGINT UNIQUE,
    long_name TEXT,
    short_name TEXT,
    hw_model TEXT,
    role TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    altitude DOUBLE PRECISION,
    battery_level INTEGER,
    voltage DOUBLE PRECISION,
    snr DOUBLE PRECISION,
    rssi DOUBLE PRECISION,
    hops_away INTEGER,
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_heard TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    source TEXT DEFAULT 'unknown',
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_nodes_last_heard ON nodes(last_heard DESC);
CREATE INDEX IF NOT EXISTS idx_nodes_location ON nodes(latitude, longitude) WHERE latitude IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_nodes_source ON nodes(source);
CREATE INDEX IF NOT EXISTS idx_nodes_active ON nodes(is_active) WHERE is_active = TRUE;

CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    altitude DOUBLE PRECISION,
    ground_speed DOUBLE PRECISION,
    ground_track DOUBLE PRECISION,
    sats_in_view INTEGER,
    precision_bits INTEGER,
    source TEXT DEFAULT 'unknown'
);

CREATE INDEX IF NOT EXISTS idx_positions_node_time ON positions(node_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_positions_timestamp ON positions(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_positions_location ON positions(latitude, longitude);

CREATE TABLE IF NOT EXISTS telemetry (
    id SERIAL PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    battery_level INTEGER,
    voltage DOUBLE PRECISION,
    channel_utilization DOUBLE PRECISION,
    air_util_tx DOUBLE PRECISION,
    temperature DOUBLE PRECISION,
    relative_humidity DOUBLE PRECISION,
    barometric_pressure DOUBLE PRECISION,
    uptime_seconds BIGINT
);

CREATE INDEX IF NOT EXISTS idx_telemetry_node_time ON telemetry(node_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    from_node TEXT NOT NULL,
    to_node TEXT,
    channel INTEGER,
    packet_id BIGINT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    message_text TEXT,
    portnum TEXT,
    want_ack BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_messages_from_node ON messages(from_node, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp DESC);

-- View for active nodes with latest position
CREATE OR REPLACE VIEW active_nodes_view AS
SELECT 
    n.*,
    p.timestamp as position_timestamp,
    p.altitude as current_altitude,
    EXTRACT(EPOCH FROM (NOW() - n.last_heard)) as seconds_since_heard
FROM nodes n
LEFT JOIN LATERAL (
    SELECT timestamp, altitude
    FROM positions
    WHERE node_id = n.node_id
    ORDER BY timestamp DESC
    LIMIT 1
) p ON TRUE
WHERE n.is_active = TRUE
ORDER BY n.last_heard DESC;

-- Function to mark old nodes as inactive
CREATE OR REPLACE FUNCTION mark_inactive_nodes()
RETURNS void AS $$
BEGIN
    UPDATE nodes
    SET is_active = FALSE
    WHERE last_heard < NOW() - INTERVAL '7 days'
    AND is_active = TRUE;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO meshuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO meshuser;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO meshuser;
