# Meshtastic Tracking System - Security Setup

## 🔒 Secrets Configuration

This project uses environment variables for sensitive configuration. **NEVER commit secrets to git!**

### Required Secrets Files

#### 1. `secrets/production.env`
Create this file with your production credentials:

```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=meshtastic
DB_USER=meshuser
DB_PASSWORD=YOUR_SECURE_DB_PASSWORD_HERE

# MQTT Configuration (Internal)
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_USER=meshlocal
MQTT_PASS=YOUR_SECURE_MQTT_PASSWORD_HERE
MQTT_TOPIC=msh/#

# API Configuration
NODE_API_KEY=YOUR_SECURE_API_KEY_HERE

# Global MQTT Bridge (mqtt.meshtastic.org)
MQTT_BRIDGE_USER=meshdev
MQTT_BRIDGE_PASS=YOUR_MESHTASTIC_ORG_PASSWORD

# Device Manager Configuration
DISCOVERY_INTERVAL=60
POLL_INTERVAL=30
MAX_FAIL_COUNT=10
AUTO_DETECT_NETWORKS=false
MANUAL_SCAN_NETWORKS=172.19.228.0/24
MESHTASTIC_TCP_PORT=4403
SERIAL_PORT=/dev/ttyUSB0
```

### 🚨 Security Checklist

Before pushing to GitHub, verify:

- [ ] `secrets/` directory is in `.gitignore` ✅
- [ ] `*.env` files are in `.gitignore` ✅
- [ ] `production.env` is NOT tracked by git
- [ ] No passwords in config files
- [ ] No API keys hardcoded in source

### Verify Secrets are Protected

```bash
# Check git status for ignored files
git status --ignored

# Should show:
# Ignored files:
#   secrets/
#   __pycache__/

# Verify production.env is NOT in git
git ls-files | grep production.env
# (should return nothing)
```

### Generate Secure Passwords

```bash
# Generate random passwords
openssl rand -base64 32

# Or use this for the production.env file:
cat > secrets/production.env << 'EOF'
DB_PASSWORD=$(openssl rand -base64 32)
MQTT_PASS=$(openssl rand -base64 32)
# ... rest of config
EOF
```

## 🔑 First Time Setup

1. Clone the repository
2. Create `secrets/` directory:
   ```bash
   mkdir -p secrets
   ```
3. Copy and edit the production.env template above
4. Set strong passwords for DB_PASSWORD and MQTT_PASS
5. Start the system:
   ```bash
   docker compose up -d
   ```

## 📝 Notes

- The `.gitignore` file protects: `secrets/`, `*.env`, `meshtracking_secrets/`
- Mosquitto password file is generated at runtime
- Database password is synchronized between PostgreSQL and application
- MQTT bridge credentials connect to mqtt.meshtastic.org public network
