-- Meshtracking Database Initialization
-- Creates all necessary tables for the all-in-one container

-- Create nodes table
CREATE TABLE IF NOT EXISTS nodes (
    id SERIAL PRIMARY KEY,
    node_id VARCHAR(20) UNIQUE NOT NULL,
    node_num BIGINT,
    short_name VARCHAR(10),
    long_name VARCHAR(50),
    hw_model VARCHAR(50),
    role INTEGER,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    altitude INTEGER,
    battery_level INTEGER,
    voltage REAL,
    snr REAL,
    rssi INTEGER,
    hops_away INTEGER,
    channel_utilization REAL,
    air_util_tx REAL,
    source VARCHAR(20),
    source_interface VARCHAR(50),
    region VARCHAR(20),
    last_seen TIMESTAMP WITH TIME ZONE,
    last_radio_contact TIMESTAMP WITH TIME ZONE,
    last_heard TIMESTAMP,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create telemetry table
CREATE TABLE IF NOT EXISTS telemetry (
    id SERIAL PRIMARY KEY,
    node_id VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    battery_level INTEGER,
    voltage REAL,
    channel_utilization REAL,
    air_util_tx REAL,
    temperature REAL,
    humidity REAL,
    pressure REAL,
    gas_resistance REAL,
    pm10 REAL,
    pm25 REAL,
    pm100 REAL,
    iaq INTEGER,
    lux REAL,
    white_lux REAL,
    ir_lux REAL,
    uv_lux REAL,
    wind_direction INTEGER,
    wind_speed REAL,
    weight REAL,
    FOREIGN KEY (node_id) REFERENCES nodes(node_id) ON DELETE CASCADE
);

-- Create messages table
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    from_node VARCHAR(20),
    to_node VARCHAR(20),
    message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    channel INTEGER,
    packet_id INTEGER,
    hop_limit INTEGER,
    want_ack BOOLEAN DEFAULT FALSE
);

-- Create node_tags table
CREATE TABLE IF NOT EXISTS node_tags (
    id SERIAL PRIMARY KEY,
    node_id VARCHAR(20) NOT NULL,
    tag VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(node_id, tag),
    FOREIGN KEY (node_id) REFERENCES nodes(node_id) ON DELETE CASCADE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_nodes_node_id ON nodes(node_id);
CREATE INDEX IF NOT EXISTS idx_nodes_last_seen ON nodes(last_seen);
CREATE INDEX IF NOT EXISTS idx_telemetry_node_id ON telemetry(node_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_from_node ON messages(from_node);

-- Grant permissions to meshuser
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO meshuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO meshuser;