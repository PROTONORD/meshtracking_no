-- Add region column to nodes table for storing LoRa region info
-- This will be populated by device_manager.py from node config

ALTER TABLE nodes ADD COLUMN IF NOT EXISTS region VARCHAR(20);

-- Add index for region filtering
CREATE INDEX IF NOT EXISTS idx_nodes_region ON nodes(region);

-- Update existing nodes: set region based on source_interface for MQTT nodes
UPDATE nodes 
SET region = 
  CASE 
    WHEN source_interface LIKE '%/EU_868/%' THEN 'EU_868'
    WHEN source_interface LIKE '%/US/%' THEN 'US'
    WHEN source_interface LIKE '%/EU_433/%' THEN 'EU_433'
    WHEN source_interface LIKE '%/TW/%' THEN 'TW'
    WHEN source_interface LIKE '%/PL/%' THEN 'PL'
    WHEN source_interface LIKE '%/CZ/%' THEN 'CZ'
    WHEN source_interface LIKE '%/KR/%' THEN 'KR'
    WHEN source_interface LIKE '%/TH/%' THEN 'TH'
    WHEN source_interface LIKE '%/BR/%' THEN 'BR'
    WHEN source_interface LIKE '%/MX/%' THEN 'MX'
    WHEN source_interface LIKE '%/msk/%' THEN 'RU'
    WHEN source_interface LIKE '%/RU/%' THEN 'RU'
    WHEN source_interface LIKE '%/ANZ/%' THEN 'ANZ'
    WHEN source_interface LIKE '%/IN/%' THEN 'IN'
    WHEN source_interface LIKE '%/JP/%' THEN 'JP'
    WHEN source_interface LIKE '%/CN/%' THEN 'CN'
    WHEN source_interface LIKE '%/SG_923/%' THEN 'SG_923'
    WHEN source_interface LIKE '%/NZ_865/%' THEN 'NZ_865'
    WHEN source_interface LIKE '%/MY_433/%' THEN 'MY_433'
    WHEN source_interface LIKE '%/MY_919/%' THEN 'MY_919'
    WHEN source_interface LIKE '%/UA_433/%' THEN 'UA_433'
    WHEN source_interface LIKE '%/UA_868/%' THEN 'UA_868'
    ELSE NULL
  END
WHERE source = 'mqtt' AND region IS NULL;
