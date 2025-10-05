#!/bin/bash
# Meshtastic Tracking System - Automated Backup Script with Rotation
# Runs daily, weekly, monthly, and yearly backups with retention policies

PROJECT_DIR="/home/meshtracking/meshtracking_no"
BACKUP_DIR="$PROJECT_DIR/secrets/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE_DAILY=$(date +%Y%m%d)
DATE_WEEKLY=$(date +%Y_W%V)
DATE_MONTHLY=$(date +%Y%m)
DATE_YEARLY=$(date +%Y)

# Backup type from argument (daily, weekly, monthly, yearly)
BACKUP_TYPE=${1:-daily}

# Create backup directories
mkdir -p "$BACKUP_DIR/daily"
mkdir -p "$BACKUP_DIR/weekly"
mkdir -p "$BACKUP_DIR/monthly"
mkdir -p "$BACKUP_DIR/yearly"

# Function to create backup
create_backup() {
    local backup_type=$1
    local backup_name=$2
    local backup_path="$BACKUP_DIR/$backup_type/$backup_name.tar.gz"
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Creating $backup_type backup: $backup_name"
    
    cd "$PROJECT_DIR"
    tar -czf "$backup_path" \
        --exclude='secrets/backups' \
        --exclude='secrets/*.tar.gz' \
        --exclude='.git' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='*.log' \
        --exclude='docker-compose.yml.backup' \
        --exclude='website_analysis.log' \
        . 2>/dev/null
    
    if [ $? -eq 0 ]; then
        local size=$(du -h "$backup_path" | cut -f1)
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ Backup created: $backup_path ($size)"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✗ Backup failed: $backup_path"
        return 1
    fi
}

# Function to rotate backups
rotate_backups() {
    local backup_type=$1
    local keep_count=$2
    local backup_path="$BACKUP_DIR/$backup_type"
    
    # Count current backups
    local current_count=$(ls -1 "$backup_path"/*.tar.gz 2>/dev/null | wc -l)
    
    if [ $current_count -gt $keep_count ]; then
        # Calculate how many to delete
        local delete_count=$((current_count - keep_count))
        
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Rotating $backup_type backups: keeping $keep_count, deleting $delete_count oldest"
        
        # Delete oldest backups
        ls -1t "$backup_path"/*.tar.gz 2>/dev/null | tail -n $delete_count | while read file; do
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Deleting old backup: $(basename $file)"
            rm -f "$file"
        done
    fi
}

# Perform backup based on type
case $BACKUP_TYPE in
    daily)
        BACKUP_NAME="meshtracking_daily_${DATE_DAILY}_${TIMESTAMP}"
        create_backup "daily" "$BACKUP_NAME"
        rotate_backups "daily" 10
        ;;
    weekly)
        BACKUP_NAME="meshtracking_weekly_${DATE_WEEKLY}"
        create_backup "weekly" "$BACKUP_NAME"
        rotate_backups "weekly" 5
        ;;
    monthly)
        BACKUP_NAME="meshtracking_monthly_${DATE_MONTHLY}"
        create_backup "monthly" "$BACKUP_NAME"
        rotate_backups "monthly" 5
        ;;
    yearly)
        BACKUP_NAME="meshtracking_yearly_${DATE_YEARLY}"
        create_backup "yearly" "$BACKUP_NAME"
        rotate_backups "yearly" 5
        ;;
    *)
        echo "Usage: $0 {daily|weekly|monthly|yearly}"
        exit 1
        ;;
esac

# Log backup summary
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup summary:"
echo "  Daily backups: $(ls -1 $BACKUP_DIR/daily/*.tar.gz 2>/dev/null | wc -l)/10"
echo "  Weekly backups: $(ls -1 $BACKUP_DIR/weekly/*.tar.gz 2>/dev/null | wc -l)/5"
echo "  Monthly backups: $(ls -1 $BACKUP_DIR/monthly/*.tar.gz 2>/dev/null | wc -l)/5"
echo "  Yearly backups: $(ls -1 $BACKUP_DIR/yearly/*.tar.gz 2>/dev/null | wc -l)/5"

exit 0
