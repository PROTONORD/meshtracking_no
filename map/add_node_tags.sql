-- Add node_tags table for custom tagging/nicknames
CREATE TABLE IF NOT EXISTS node_tags (
    id SERIAL PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    tag_type TEXT DEFAULT 'custom', -- 'nickname', 'category', 'custom'
    color TEXT DEFAULT '#3B82F6',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(node_id, tag)
);

-- Index for fast tag search
CREATE INDEX IF NOT EXISTS idx_node_tags_tag ON node_tags(tag);
CREATE INDEX IF NOT EXISTS idx_node_tags_node_id ON node_tags(node_id);
CREATE INDEX IF NOT EXISTS idx_node_tags_type ON node_tags(tag_type);

-- Add custom fields to nodes table
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS manual_latitude DOUBLE PRECISION;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS manual_longitude DOUBLE PRECISION;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS manual_altitude DOUBLE PRECISION;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS manual_address TEXT;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS position_source TEXT DEFAULT 'gps'; -- 'gps', 'manual', 'address'

-- Create function to get effective position (manual overrides GPS)
CREATE OR REPLACE FUNCTION get_effective_position(n nodes)
RETURNS TABLE(lat DOUBLE PRECISION, lon DOUBLE PRECISION, alt DOUBLE PRECISION, source TEXT) AS $$
BEGIN
    IF n.manual_latitude IS NOT NULL AND n.manual_longitude IS NOT NULL THEN
        RETURN QUERY SELECT n.manual_latitude, n.manual_longitude, n.manual_altitude, 'manual'::TEXT;
    ELSE
        RETURN QUERY SELECT n.latitude, n.longitude, n.altitude, 'gps'::TEXT;
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Create view for nodes with their tags (easier querying)
CREATE OR REPLACE VIEW nodes_with_tags AS
SELECT 
    n.*,
    -- Use manual position if set, otherwise GPS position
    COALESCE(n.manual_latitude, n.latitude) as effective_latitude,
    COALESCE(n.manual_longitude, n.longitude) as effective_longitude,
    COALESCE(n.manual_altitude, n.altitude) as effective_altitude,
    CASE 
        WHEN n.manual_latitude IS NOT NULL THEN 'manual'
        WHEN n.latitude IS NOT NULL THEN 'gps'
        ELSE NULL
    END as effective_position_source,
    COALESCE(
        json_agg(
            json_build_object(
                'tag', nt.tag,
                'type', nt.tag_type,
                'color', nt.color
            ) ORDER BY nt.tag_type, nt.tag
        ) FILTER (WHERE nt.tag IS NOT NULL),
        '[]'::json
    ) as tags
FROM nodes n
LEFT JOIN node_tags nt ON n.node_id = nt.node_id
GROUP BY n.node_id;

COMMENT ON TABLE node_tags IS 'Custom tags/nicknames for nodes - for personal/group identification';
COMMENT ON COLUMN node_tags.tag_type IS 'nickname=main name, category=group (e.g. "jakt", "familie"), custom=other tags';
COMMENT ON COLUMN nodes.notes IS 'Free-form notes about the node';
COMMENT ON COLUMN nodes.manual_latitude IS 'Manually set latitude - overrides GPS position';
COMMENT ON COLUMN nodes.manual_longitude IS 'Manually set longitude - overrides GPS position';
COMMENT ON COLUMN nodes.manual_address IS 'Manual address (can be geocoded to coordinates)';
COMMENT ON COLUMN nodes.position_source IS 'Source of position: gps, manual, or address';
