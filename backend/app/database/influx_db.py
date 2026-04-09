from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from app.core.config import settings
from app.models.alert import AlertData 
from app.models.sensor import SensorData
from influxdb_client.client.query_api import QueryApi
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)
client = InfluxDBClient(url="http://localhost:32086", token=settings.INFLUX_TOKEN, org=settings.INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()  

def get_all_devices():
    query = f"""
        import "influxdata/influxdb/schema"
        schema.tagValues(bucket: "{settings.INFLUX_BUCKET}", tag: "device_id")
    """
    try:
        tabelas = query_api.query(query=query, org=settings.INFLUX_ORG)
        dispositivos = [registo.get_value() for tabela in tabelas for registo in tabela.records]
        return dispositivos
    except Exception as e:
        logger.error(f"Erro ao listar dispositivos: {e}")
        return []
    
def get_latest_device_state(device_id: str):
    query = f"""
        from(bucket: "{settings.INFLUX_BUCKET}")
          |> range(start: -24h)
          |> filter(fn: (r) => r["_measurement"] == "Sensor")
          |> filter(fn: (r) => r["device_id"] == "{device_id}")
          |> last()
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    """
    try:
        tabelas = query_api.query(query=query, org=settings.INFLUX_ORG)
        for tabela in tabelas:
            for registo in tabela.records:
                return {
                    "timestamp": registo.get_time().isoformat(),
                    "device_id": registo.values.get("device_id"),
                    "lat": registo.values.get("lat"),
                    "lon": registo.values.get("lon"),
                    "speed": registo.values.get("speed"),
                    "accel_x": registo.values.get("accel_x"),
                    "accel_y": registo.values.get("accel_y"),
                    "accel_z": registo.values.get("accel_z")
                }
        return None
    except Exception as e:
        logger.error(f"Erro ao obter último estado do {device_id}: {e}")
        return None
    

def get_latest_device_state(device_id: str):
    """Obtém a última telemetria conhecida de um dispositivo."""
    query = f"""
        from(bucket: "{settings.INFLUX_BUCKET}")
          |> range(start: -24h) // Procura na última janela de 24h
          |> filter(fn: (r) => r["_measurement"] == "Sensor")
          |> filter(fn: (r) => r["device_id"] == "{device_id}")
          |> last()
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    """
    try:
        tabelas = query_api.query(query=query, org=settings.INFLUX_ORG)
        for tabela in tabelas:
            for registo in tabela.records:
                return {
                    "timestamp": registo.get_time().isoformat(),
                    "device_id": registo.values.get("device_id"),
                    "lat": registo.values.get("lat"),
                    "lon": registo.values.get("lon"),
                    "speed": registo.values.get("speed"),
                    "accel_x": registo.values.get("accel_x"),
                    "accel_y": registo.values.get("accel_y"),
                    "accel_z": registo.values.get("accel_z")
                }
        return None
    except Exception as e:
        logger.error(f"Erro ao obter último estado do {device_id}: {e}")
        return None

def get_device_history(device_id: str, start: str, end: str):
    query = f"""
        from(bucket: "{settings.INFLUX_BUCKET}")
          |> range(start: {start}, stop: {end})
          |> filter(fn: (r) => r["_measurement"] == "Sensor")
          |> filter(fn: (r) => r["device_id"] == "{device_id}")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    """
    try:
        tabelas = query_api.query(query=query, org=settings.INFLUX_ORG)
        resultados = []
        for tabela in tabelas:
            for registo in tabela.records:
                resultados.append({
                    "timestamp": registo.get_time().isoformat(),
                    "speed": registo.values.get("speed"),
                    "lat": registo.values.get("lat"),
                    "lon": registo.values.get("lon")
                })
        return resultados
    except Exception as e:
        logger.error(f"Erro ao obter histórico de {device_id}: {e}")
        return []
    
    
        
def save_alert_data(data: AlertData):
    ponto = (
        Point("Alert")
        .tag("device_id", data.device_id)
        .tag("source", data.source)
        .tag("type", data.type).
         tag("event_type",data.event_type)
        .tag("trigger", data.trigger)
        .field("lat", data.lat)
        .field("lon", data.lon)
    )

    if data.timestamp:
        ponto = ponto.time(data.timestamp, WritePrecision.NS)

    try:
        write_api.write(
            bucket=settings.INFLUX_BUCKET,
            org=settings.INFLUX_ORG,
            record=ponto
        )
        logger.info(f"✅ Alerta {data.device_id} gravado no InfluxDB!")
    except Exception as e:
        logger.info(f"❌ Erro ao gravar no InfluxDB: {e}")
        
        
def save_sensor_data(data: SensorData):
    ponto = (
        Point("Sensor")
        .tag("device_id", data.device_id)
        .tag("source", data.source)
        .tag("type", data.type)
        .field("lat", data.lat)
        .field("lon", data.lon)
        .field("speed", data.speed)
        .field("accel_x", data.accel_x)
        .field("accel_y", data.accel_y)
        .field("accel_z", data.accel_z)
    )

    if data.timestamp:
        ponto = ponto.time(data.timestamp, WritePrecision.NS)

    try:
        write_api.write(
            bucket=settings.INFLUX_BUCKET,
            org=settings.INFLUX_ORG,
            record=ponto
        )
        logger.info(f"✅ Sensor {data.device_id} gravado no InfluxDB!")
    except Exception as e:
        logger.info(f"❌ Erro ao gravar no InfluxDB: {e}")        
        
        

def get_recent_alerts(minutos: int, device_id: Optional[str] = None):
    query_lines = [
        f'from(bucket: "{settings.INFLUX_BUCKET}")',
        f'  |> range(start: -{minutos}m)',
        '  |> filter(fn: (r) => r["_measurement"] == "Alert")'
    ]
    
    if device_id:
        query_lines.append(f'  |> filter(fn: (r) => r["device_id"] == "{device_id}")')
        
    query_lines.append('  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")')
    query = "\n".join(query_lines)
    
    try:
        tabelas = query_api.query(query=query, org=settings.INFLUX_ORG)
        resultados = []
        for tabela in tabelas:
            for registo in tabela.records:
                resultados.append({
                    "timestamp": registo.get_time().isoformat(),
                    "device_id": registo.values.get("device_id"),
                    "type": registo.values.get("type"),  
                    "event_type": registo.values.get("event_type"),
                    "trigger": registo.values.get("trigger"),
                    "lat": registo.values.get("lat"),
                    "lon": registo.values.get("lon")
                })
        return resultados
    except Exception as e:
        logger.error(f"Erro ao ler alertas do InfluxDB: {e}")
        return []
    
def get_recent_sensor_data(minutos: int,device_id: Optional[str] = None):
    query = f"""
        from(bucket: "{settings.INFLUX_BUCKET}")
          |> range(start: -{minutos}m)
          |> filter(fn: (r) => r["_measurement"] == "Sensor")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    """
    
    if device_id:
        query.append(f'  |> filter(fn: (r) => r["device_id"] == "{device_id}")')
        
    query += ('  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")')
    query = "\n".join(query)
    
    try:
        tabelas = query_api.query(query=query, org=settings.INFLUX_ORG)
        resultados = []
        for tabela in tabelas:
            for registo in tabela.records:
                resultados.append({
                    "timestamp": registo.get_time().isoformat(),
                    "device_id": registo.values.get("device_id"), # Tag
                    "type": registo.values.get("type"),           # Tag
                    "trigger": registo.values.get("trigger"),     # Tag
                    "lat": registo.values.get("lat"),             # Field
                    "lon": registo.values.get("lon") ,
                    "speed": registo.values.get("speed"),
                    "accel_x": registo.values.get("accel_x")       ,
                    "accel_y": registo.values.get("accel_y"),
                    "accel_z": registo.values.get("accel_z")
     
       

                })
        return resultados
    except Exception as e:
        logger.info(f" Erro ao ler do InfluxDB: {e}")
        return []


def get_alerts_stats():
    query = f"""
        from(bucket: "{settings.INFLUX_BUCKET}")
          |> range(start: -30d)
          |> filter(fn: (r) => r["_measurement"] == "Alert")
          |> group(columns: ["event_type"])
          |> count()
    """
    try:
        tabelas = query_api.query(query=query, org=settings.INFLUX_ORG)
        estatisticas = {}
        for tabela in tabelas:
            for registo in tabela.records:
                evento = registo.values.get("event_type")
                # O InfluxDB coloca a contagem na coluna '_value' após a função count()
                estatisticas[evento] = registo.values.get("_value")
        return estatisticas
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas de alertas: {e}")
        return {}
    
def close_db_client():
    write_api.close()
    query_api.close()
    client.close()
    logger.info("Ligação ao InfluxDB encerrada.")