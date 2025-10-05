# File Locations for index.html

## Production Setup (Current)

### 1. Source File (Development)
- **Location**: `/home/meshtracking/meshtracking_no/index.html`
- **Purpose**: Main development file, edited by developers
- **Current Version**: 3.27.6

### 2. Container - /app/index.html
- **Location**: Container `/app/index.html`
- **Purpose**: Copied during Docker build from source
- **Mounted**: Via volume mount in docker-compose.yml (optional)
- **Current Version**: 3.27.6

### 3. Container - /data/index.html (ACTIVE)
- **Location**: Container `/data/index.html` 
- **Purpose**: **THIS IS WHAT FLASK SERVES** - Flask serves from DATA_DIR='/data'
- **Mounted**: Via volume mount in docker-compose.yml: `./index.html:/data/index.html`
- **Current Version**: 3.27.6
- **⚠️ CRITICAL**: This is the file users see!

### 4. Docker Volume - meshtracking_data
- **Location**: Docker volume `meshtracking_no_meshtracking_data`
- **Purpose**: Persistent storage, survives container restarts
- **Contains**: /data/index.html (same as #3)
- **Current Version**: 3.27.6

## Deployment Workflow

### Development (Live Updates)
```bash
# Edit the source file
vim /home/meshtracking/meshtracking_no/index.html

# Changes are immediately reflected because of volume mount:
# ./index.html:/data/index.html
# No restart needed, just hard-refresh browser (Ctrl+Shift+R)
```

### Production (Docker Rebuild)
```bash
# When rebuilding from scratch:
cd /home/meshtracking/meshtracking_no
docker compose down
docker compose build --no-cache
docker compose up -d

# Dockerfile will:
# 1. Copy index.html to /app/index.html (line 44)
# 2. Copy index.html to /data/index.html (line 61)
```

## Verification Commands

```bash
# Check source file version
head -4 /home/meshtracking/meshtracking_no/index.html | grep VERSION

# Check container /app version
docker exec meshtracking head -4 /app/index.html | grep VERSION

# Check container /data version (ACTIVE)
docker exec meshtracking head -4 /data/index.html | grep VERSION

# Check what web server serves
curl -s http://localhost:8088/ | grep VERSION | head -1

# Check Docker volume
docker run --rm -v meshtracking_no_meshtracking_data:/data alpine head -4 /data/index.html | grep VERSION
```

## Important Notes

1. **Flask serves from /data**: combined_server.py has `DATA_DIR = '/data'`
2. **Volume mount overrides**: The mount `./index.html:/data/index.html` means changes to source file are immediately reflected
3. **Backup files**: Old backups exist with pattern `index.html.backup-*`, ignored by Docker
4. **No need to restart**: With volume mount, just hard-refresh browser (Ctrl+Shift+R)

## Version History (Recent)
- v3.27.6: Fixed API endpoint from /api/nodes/geojson to /nodes.geojson
- v3.27.5: Fixed duplicate source filter IDs
- v3.27.4: Favorites use status colors, no special label styling
- v3.27.3: Removed gold ring for favorites
- v3.27.2: Fixed color determination logic
- v3.24.0: Desktop-only mode enforced
- v3.25.0: Favorite star buttons added
- v3.26.0: Favorites persist via localStorage
