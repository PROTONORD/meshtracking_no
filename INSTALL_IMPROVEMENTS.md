# Installasjonsinstruksjoner for forbedringer

## 1. USB udev rules (KRITISK - anbefales sterkt)

Dette sikrer at USB-enheten alltid har samme device path, selv etter frakobling eller reboot.

```bash
# Installer udev rule
sudo cp 99-meshtastic.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger

# Verifiser at symlink er opprettet
ls -la /dev/meshtastic-usb
# Skal vise: /dev/meshtastic-usb -> ttyUSB0
```

**Deretter oppdater docker-compose.yml** (gjøres ved neste rebuild):
```yaml
devices:
  - /dev/meshtastic-usb:/dev/ttyUSB0  # Bruk stabil symlink i stedet for ttyUSB0
```

## 2. Appliser forbedringer

Forbedringene er allerede lagt til i filene. For å aktivere dem:

```bash
# Rebuild og restart containere med nye forbedringer
cd /home/kau005/meshtastic-docker
docker-compose down
docker-compose up -d --build

# Verifiser at alle containere kjører
docker ps | grep meshtastic

# Sjekk healthcheck status (vent 1 minutt)
docker ps --format "table {{.Names}}\t{{.Status}}"
```

## 3. Test health check script

```bash
cd /home/kau005/meshtastic-docker
./health_check.sh
```

## 4. Sett opp cron for ukentlig health check (valgfritt)

```bash
# Legg til i crontab
crontab -e

# Legg til denne linjen (kjører hver mandag kl 08:00)
0 8 * * 1 /home/kau005/meshtastic-docker/health_check.sh 2>&1 | logger -t meshtastic-health
```

## 5. Verifiser at backup kjører

Første backup vil kjøre kl 02:00 neste natt. For å teste nå:

```bash
# Test backup manuelt
docker exec meshtastic-map sh -c "mkdir -p /data/backup && PGPASSWORD=meshpass2025 pg_dump -h postgres -U meshuser meshtastic | gzip > /data/backup/db_test_$(date +%Y%m%d_%H%M%S).sql.gz"

# Sjekk at backup ble opprettet
ls -lh /home/kau005/meshtastic-data/backup/
```

## 6. Test recovery prosedyre (simulert)

```bash
# Simuler container restart (test restart policy)
docker restart meshtastic-map
sleep 10
docker ps | grep meshtastic-map

# Sjekk at alle prosesser kjører igjen
docker exec meshtastic-map sh -c "ls -la /proc/*/exe 2>/dev/null | grep python | wc -l"
# Skal vise: 6

# Test database restore (fra backup)
# MERK: Dette sletter eksisterende data, kun for testing!
# gunzip < /home/kau005/meshtastic-data/backup/db_YYYYMMDD_HHMMSS.sql.gz | docker exec -i meshtastic-postgres psql -U meshuser meshtastic
```

## Nye features aktivert

✅ **Healthcheck**: meshmap container har nå healthcheck som sjekker at web server svarer  
✅ **Logging limits**: Alle containere har 50MB max log size, 3 filer rotasjon  
✅ **Database backup**: Kjører automatisk kl 02:00 hver natt, beholder 14 dager  
✅ **Health check script**: Omfattende systemsjekk tilgjengelig via `./health_check.sh`  
✅ **USB udev rules**: Sikrer stabil device path (krever installasjon)

## Verifisering

Sjekk at alt fungerer:

```bash
# 1. Containere kjører og er healthy
docker ps --format "table {{.Names}}\t{{.Status}}"

# 2. Python-prosesser
docker exec meshtastic-map sh -c "ls -la /proc/*/exe 2>/dev/null | grep python | wc -l"
# Forventet: 6

# 3. Database tilkobling
docker exec meshtastic-postgres pg_isready -U meshuser -d meshtastic

# 4. GeoJSON oppdateres
ls -lh /home/kau005/meshtastic-data/nodes.geojson

# 5. Kjør full health check
./health_check.sh
```

## Troubleshooting

### Container ikke healthy
```bash
docker ps -a
docker logs meshtastic-map --tail 50
docker-compose restart meshmap
```

### Backup feiler
```bash
# Sjekk at backup directory eksisterer
docker exec meshtastic-map ls -la /data/backup/

# Sjekk database tilkobling
docker exec meshtastic-map sh -c "PGPASSWORD=meshpass2025 pg_dump -h postgres -U meshuser meshtastic --schema-only" | head -20
```

### USB-enhet ikke tilgjengelig
```bash
# Sjekk at enheten er tilkoblet
ls -la /dev/ttyUSB* /dev/meshtastic-usb

# Sjekk permissions
groups | grep dialout

# Sjekk udev rule
cat /etc/udev/rules.d/99-meshtastic.rules
```

## Neste steg

1. Appliser endringene: `docker-compose up -d --build`
2. Installer udev rules (se over)
3. Test health check: `./health_check.sh`
4. Vent til neste natt og verifiser at backup kjører
5. Sett opp ukentlig health check i cron (valgfritt)

Se `HEALTH_CHECK.md` for detaljert dokumentasjon.
