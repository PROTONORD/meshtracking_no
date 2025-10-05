#!/bin/bash

# PROTONORD Meshtastic Node Configuration Script
# Based on IBICO74/meshtastic-python-script methodology
# Configures USB node with proper settings for message reception

set -e

NODE_PORT="/dev/ttyUSB0"
LOG_FILE="/tmp/meshtastic_config_$(date +%Y%m%d_%H%M%S).log"
PAUSE_SECS=5

echo "🔧 PROTONORD Meshtastic Node Configuration Script" | tee -a "${LOG_FILE}"
echo "📝 Port: ${NODE_PORT}" | tee -a "${LOG_FILE}"
echo "📄 Log: ${LOG_FILE}" | tee -a "${LOG_FILE}"
echo "---------------------------------------------------" | tee -a "${LOG_FILE}"

# Function to safely execute meshtastic commands with proper error handling
safe_command() {
    local cmd="$1"
    local description="$2"
    
    echo "🔄 ${description}" | tee -a "${LOG_FILE}"
    echo "   Command: ${cmd}" | tee -a "${LOG_FILE}"
    
    if eval "${cmd}" 2>&1 | tee -a "${LOG_FILE}"; then
        echo "   ✅ Success" | tee -a "${LOG_FILE}"
        echo "" | tee -a "${LOG_FILE}"
        sleep "${PAUSE_SECS}"
        return 0
    else
        echo "   ❌ Failed" | tee -a "${LOG_FILE}"
        echo "" | tee -a "${LOG_FILE}"
        sleep "${PAUSE_SECS}"
        return 1
    fi
}

# Function to get current setting value
get_setting() {
    local setting="$1"
    echo "📊 Getting current value of ${setting}:" | tee -a "${LOG_FILE}"
    meshtastic --port "${NODE_PORT}" --get "${setting}" 2>&1 | tee -a "${LOG_FILE}"
    echo "" | tee -a "${LOG_FILE}"
    sleep "${PAUSE_SECS}"
}

# Function to set configuration with verification
set_setting() {
    local setting="$1" 
    local value="$2"
    local description="$3"
    
    echo "🔧 Setting ${setting} = ${value}" | tee -a "${LOG_FILE}"
    echo "   Description: ${description}" | tee -a "${LOG_FILE}"
    
    # Set the value
    if safe_command "meshtastic --port '${NODE_PORT}' --set '${setting}' '${value}'" "Setting ${setting}"; then
        echo "   ⏰ Waiting for setting to be applied..." | tee -a "${LOG_FILE}"
        sleep 10
        
        # Verify the setting was applied
        echo "   🔍 Verifying setting was applied:" | tee -a "${LOG_FILE}"
        get_setting "${setting}"
        return 0
    else
        echo "   ❌ Failed to set ${setting}" | tee -a "${LOG_FILE}"
        return 1
    fi
}

# Main configuration sequence
echo "🚀 Starting configuration sequence..." | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"

# 1. Get current device info
echo "=== CURRENT DEVICE INFO ===" | tee -a "${LOG_FILE}"
safe_command "meshtastic --port '${NODE_PORT}' --info" "Getting device info"

# 2. Get current problematic settings
echo "=== CURRENT PROBLEMATIC SETTINGS ===" | tee -a "${LOG_FILE}"
get_setting "device.role"
get_setting "channel.downlink_enabled"
get_setting "channel.uplink_enabled"
get_setting "lora.region"

# 3. Fix device role (most critical)
echo "=== FIXING DEVICE ROLE ===" | tee -a "${LOG_FILE}"
echo "📝 Changing device role from CLIENT_HIDDEN (8) to CLIENT (1)" | tee -a "${LOG_FILE}"
echo "   This allows the node to receive and process messages normally" | tee -a "${LOG_FILE}"

if set_setting "device.role" "1" "Change to CLIENT role for message reception"; then
    echo "✅ Device role change initiated" | tee -a "${LOG_FILE}"
    echo "⚠️  Node may reboot to apply role change..." | tee -a "${LOG_FILE}"
    echo "⏰ Waiting 30 seconds for potential reboot..." | tee -a "${LOG_FILE}"
    sleep 30
else
    echo "❌ Failed to change device role" | tee -a "${LOG_FILE}"
fi

# 4. Try to reconnect and verify role change
echo "=== VERIFYING ROLE CHANGE ===" | tee -a "${LOG_FILE}"
echo "🔄 Attempting to reconnect and verify role change..." | tee -a "${LOG_FILE}"
sleep 10

get_setting "device.role"

# 5. Configure channels for bi-directional communication
echo "=== CONFIGURING CHANNELS ===" | tee -a "${LOG_FILE}"
echo "📝 Enabling uplink and downlink on default channel" | tee -a "${LOG_FILE}"
echo "   This allows the node to send and receive messages" | tee -a "${LOG_FILE}"

# Enable uplink on channel 0
set_setting "channel.uplink_enabled" "true" "Enable uplink for message sending"

# Enable downlink on channel 0  
set_setting "channel.downlink_enabled" "true" "Enable downlink for message receiving"

# 6. Verify LoRa region is correct
echo "=== VERIFYING LORA REGION ===" | tee -a "${LOG_FILE}"
get_setting "lora.region"

# Check if region needs to be set
echo "🔍 Checking if LoRa region needs to be set to EU_868..." | tee -a "${LOG_FILE}"
current_region=$(meshtastic --port "${NODE_PORT}" --get "lora.region" 2>/dev/null | grep -o "region: [0-9]*" | cut -d' ' -f2 || echo "unknown")

if [ "$current_region" != "3" ]; then
    echo "⚠️  LoRa region is ${current_region}, setting to 3 (EU_868)" | tee -a "${LOG_FILE}"
    set_setting "lora.region" "3" "Set LoRa region to EU_868 for Norway"
else
    echo "✅ LoRa region already correctly set to EU_868" | tee -a "${LOG_FILE}"
fi

# 7. Final verification
echo "=== FINAL VERIFICATION ===" | tee -a "${LOG_FILE}"
echo "🔍 Checking all critical settings after configuration..." | tee -a "${LOG_FILE}"

get_setting "device.role"
get_setting "channel.uplink_enabled" 
get_setting "channel.downlink_enabled"
get_setting "lora.region"
get_setting "lora.tx_enabled"

# 8. Configuration summary
echo "=== CONFIGURATION SUMMARY ===" | tee -a "${LOG_FILE}"
echo "📋 Configuration completed for PROTONORD USB node" | tee -a "${LOG_FILE}"
echo "🎯 Key changes made:" | tee -a "${LOG_FILE}"
echo "   • Device role set to CLIENT (1) for message reception" | tee -a "${LOG_FILE}"
echo "   • Channel uplink/downlink enabled for bi-directional communication" | tee -a "${LOG_FILE}"
echo "   • LoRa region verified as EU_868 (3)" | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"
echo "⚠️  IMPORTANT: Node may need to reboot to fully apply all changes" | tee -a "${LOG_FILE}"
echo "📄 Full log saved to: ${LOG_FILE}" | tee -a "${LOG_FILE}"
echo "✅ Configuration script completed!" | tee -a "${LOG_FILE}"

exit 0