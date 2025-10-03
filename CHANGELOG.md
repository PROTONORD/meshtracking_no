# Changelog

All notable changes to the Meshtastic Docker System will be documented in this file.

## [3.4.4] - 2025-10-04

### 🚀 Revolutionary Interface Changes
- **BREAKING**: Combined node and label into single clickable component
- **NEW**: Embedded status icons using CSS pseudo-elements
- **NEW**: Always visible labels (removed zoom restrictions)
- **IMPROVED**: Single-click interaction model (no separate markers)

### 🔧 Technical Improvements
- **FIXED**: Popup functionality with consistent coordinate handling
- **FIXED**: Icon size issues that prevented rendering
- **OPTIMIZED**: Rendering performance and reliability
- **CLEANED**: Removed debug logging for production

### 🎨 Design Enhancements
- **NEW**: Status-integrated icons in node labels
- **IMPROVED**: Better padding and spacing for embedded icons
- **ENHANCED**: Mobile responsive design optimization
- **REFINED**: Hover effects and transitions

## [3.4.3] - 2025-10-04
### 🔍 Emergency Debug Version
- **DEBUG**: Extensive logging for troubleshooting node visibility
- **TEMP**: Always show labels regardless of zoom for debugging

## [3.4.2] - 2025-10-04
### 🔍 Debug Improvements
- **DEBUG**: Added comprehensive logging for node rendering
- **FIXED**: Icon size from null to fixed dimensions
- **LOWERED**: Zoom threshold from 8 to 6 for better visibility

## [3.4.1] - 2025-10-04
### 🔧 Bug Fixes
- **FIXED**: Popup functionality and coordinate consistency
- **IMPROVED**: Coordinate handling using geometry coordinates

## [3.4.0] - 2025-10-04
### 🚀 Revolutionary Combined Interface
- **BREAKING**: Eliminated separate node markers
- **NEW**: Combined node+label unified interface
- **NEW**: Status icons integrated in labels

## [3.3.6] - 2025-10-03
### 🔧 CSS Transform Positioning
- **FIXED**: Navnelapp positioning using CSS transforms
- **NEW**: Stacked label positioning system

## [3.3.5] - 2025-10-03
### 👁️ Visibility Improvements
- **FIXED**: Navnelapp visibility issues
- **LOWERED**: Zoom threshold from 10 to 8

## [3.3.4] - 2025-10-03
### 📍 Positioning Fixes
- **FIXED**: Navnelapp positioning calculations
- **IMPROVED**: IconAnchor positioning logic

## [3.3.3] - 2025-10-03
### 🌟 Orbital Popup System
- **NEW**: Revolutionary 8-pod circular popup layout
- **NEW**: Central clickable nodes
- **NEW**: Floating animations with golden hover effects

## [3.3.2] - 2025-10-03
### 🔍 Search & Navigation
- **FIXED**: Client-side search with auto-zoom
- **IMPROVED**: Navnelapp click handling

## [3.3.1] - 2025-10-03
### 🐛 Critical Bug Fixes
- **FIXED**: JavaScript errors (createNodeMarker undefined)
- **FIXED**: Coordinate validation with null checks

## [3.3.0] - 2025-10-03
### 📱 Mobile Optimization
- **NEW**: Responsive popup sizing
- **IMPROVED**: Mobile touch interactions

## [3.2.2] - 2025-10-03

### 🎯 Major Features Added
- **Comprehensive Live Telemetry** - 6 categories with 30+ sensor types
- **Client-side Search** - Real-time search with auto-zoom functionality
- **Enhanced Navigation** - Clickable labels with improved z-index handling
- **Extended Data Retention** - 60-day storage period (up from 2 weeks)
- **Dead Node Indicators** - Visual 💀 marking for nodes offline 2+ weeks

### 🗺️ Telemetry Categories Implemented
- 🌡️ **Temperature & Environment** (temperature, humidity, pressure, gas resistance)
- 🔋 **Power & Battery** (battery level, voltage, current, power consumption)
- 🌬️ **Air Quality** (PM1.0, PM2.5, PM10, IAQ index)
- ☀️ **Weather & Outdoor** (wind direction/speed, rain hourly, UV index)
- 💡 **Light & Sensors** (lux, PIR, ambient light, solar irradiance)
- 📡 **Network & Connectivity** (SNR, altitude, channel utilization, air util TX)

### 📍 Navigation Improvements
- Client-side search with real-time node filtering
- Auto-zoom to search results with smooth 0.8s animation
- Automatic popup opening for selected nodes
- Enhanced label stacking with 25px vertical spacing
- Improved z-index handling (1000/1001) for overlapping elements

### 💾 Data Management Enhancements
- PostgreSQL backend with comprehensive telemetry schema
- Live updates every 10 seconds when popup is open
- All sensor categories always visible with N/A for missing data
- Flash effects for updated telemetry values

### 🔧 Bug Fixes
- Fixed `createNodeMarker` function missing error
- Resolved search API endpoint (implemented client-side solution)
- Enhanced CSS for clickable labels with `pointer-events: auto`
- Improved label hover effects and scaling

### 🏗️ System Architecture
- Production-ready container orchestration
- Auto-recovery from common failure modes
- Health monitoring every 60 seconds
- Complete documentation suite

### 📊 Current System Performance
- **Total Nodes**: 1,978+ registered
- **Active Nodes**: 700+ (last 24 hours)
- **Telemetry Entries**: 10,500+ measurements
- **Health Score**: 9.5/10
- **Uptime**: Auto-recovery from all common failures

---

## [3.1.x] - 2025-10-03

### Added
- Live telemetry implementation
- Dead node indicators with visual marking
- PostgreSQL migration from SQLite
- Enhanced mobile/desktop UI

### Changed
- Extended data retention to 60 days
- Improved node status system (online/recent/offline/dead)

---

## [3.0.x] - 2025-10-03

### Added
- Major system overhaul with PostgreSQL
- Multi-source data collection (MQTT, USB, WiFi)
- Comprehensive health checks and monitoring
- Auto-recovery capabilities

### Changed
- Migrated from SQLite to PostgreSQL
- Enhanced container architecture
- Improved documentation structure

---

## Previous Versions

Earlier versions focused on basic MQTT collection and SQLite storage. See git history for detailed changes before v3.0.

---

**Legend:**
- 🎯 Major Features
- 🗺️ Map/UI Improvements  
- 📍 Navigation/Search
- 💾 Data/Backend
- 🔧 Bug Fixes
- 🏗️ Infrastructure
- 📊 Performance/Stats