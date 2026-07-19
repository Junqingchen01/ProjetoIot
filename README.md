# Projeto IoT P01 - Comandos

## Preparar

```powershell
cd ProjetoIot
Copy-Item env.example .env
```

## Stack Docker

```powershell
docker compose up -d --build
```

```powershell
docker compose ps
docker compose logs -f backend
docker compose logs -f simulator
docker compose restart simulator
docker compose down
```

```powershell
docker compose down -v
```

## Abrir Servicos

```powershell
start http://localhost:8080/?api_key=iot
start http://localhost:8000/health
start http://localhost:8000/health/ready
start http://localhost:18086
```

## Defaults De Demo

```powershell
API key: iot
MQTT username: iot
MQTT password: iot
InfluxDB username: admin
InfluxDB password: adminadmin
InfluxDB token: adminadmin
```

## Health Checks

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/health/ready
```

## MQTT TLS

```powershell
docker cp iot-mosquitto:/mosquitto/data/tls/ca.crt .\mosquitto-ca.crt
Test-NetConnection localhost -Port 1883
Test-NetConnection localhost -Port 8883
```

## Simulador Docker

```powershell
docker compose up -d --build simulator
docker logs iot-simulator --tail 40
docker logs -f iot-simulator
```

## Simulador Local

```powershell
python simulate_fleet.py --mode mqtt --mqtt-tls --mqtt-ca-cert .\mosquitto-ca.crt --mqtt-host localhost --mqtt-port 8883 --fleet-size 16 --speedup 5 --selection random --publish-truth-alerts
```

```powershell
python simulate_fleet.py --mode rest --api-key iot --fleet-size 16 --speedup 5 --selection random
```

## Importar Datasets

```powershell
python import_dataset.py --mode dry-run
```

```powershell
python import_dataset.py --mode rest --api-key iot --scenario fall_accident_001
```

```powershell
python import_dataset.py --mode mqtt --mqtt-tls --mqtt-ca-cert .\mosquitto-ca.crt --mqtt-host localhost --mqtt-port 8883 --mqtt-username iot --mqtt-password iot --scenario fall_accident_001 --publish-truth-alerts
```

```powershell
python import_dataset.py --mode mqtt --mqtt-tls --mqtt-ca-cert .\mosquitto-ca.crt --mqtt-host localhost --mqtt-port 8883 --mqtt-username iot --mqtt-password iot
```

## Testes

```powershell
python scripts\validate_braga_datasets.py --strict
python -m unittest discover -s tests
python scripts\smoke_test_stack.py
python scripts\measure_alert_latency.py --api-key iot
```

## Consultas API

```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/qos/status" -Headers @{"X-API-Key"="iot"} | ConvertTo-Json -Depth 4
```

```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/sessions/summary?minutos=60" -Headers @{"X-API-Key"="iot"} | ConvertTo-Json -Depth 4
```

```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/devices/status?minutos=5&offline_after_sec=45" -Headers @{"X-API-Key"="iot"} | ConvertTo-Json -Depth 5
```

```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/sensors?minutos=10" -Headers @{"X-API-Key"="iot"} | ConvertTo-Json -Depth 4
```

```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/alerts?minutos=60" -Headers @{"X-API-Key"="iot"} | ConvertTo-Json -Depth 4
```

```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/alerts?minutos=60&event_type=dock_data_dump" -Headers @{"X-API-Key"="iot"} | ConvertTo-Json -Depth 4
```

## Backend Local

```powershell
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Rebuild Parcial

```powershell
docker compose up -d --build backend
docker compose up -d --build dashboard
docker compose up -d --build simulator
```
