from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from app.core.config import settings
from app.models.alert import AlertData 
from app.models.sensor import SensorData
from influxdb_client.client.query_api import QueryApi

client = InfluxDBClient(url="http://localhost:32086", token=settings.INFLUX_TOKEN, org=settings.INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()  

def save_alert_data(data: AlertData):
    ponto = (
        Point("Alert")
        .tag("device_id", data.device_id)
        .tag("source", data.source)
        .tag("type", data.type)
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
        print(f"✅ Alerta {data.device_id} gravado no InfluxDB!")
    except Exception as e:
        print(f"❌ Erro ao gravar no InfluxDB: {e}")
        
        
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
        print(f"✅ Sensor {data.device_id} gravado no InfluxDB!")
    except Exception as e:
        print(f"❌ Erro ao gravar no InfluxDB: {e}")        
        
        

def get_recent_alerts(minutos: int):
    # Removido o pivot complexo para teste ou ajustado para incluir tags
    query = f"""
        from(bucket: "{settings.INFLUX_BUCKET}")
          |> range(start: -{minutos}m)
          |> filter(fn: (r) => r["_measurement"] == "Alert")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    """
    
    try:
        tabelas = query_api.query(query=query, org=settings.INFLUX_ORG)
        resultados = []
        for tabela in tabelas:
            for registo in tabela.records:
                # O InfluxDB coloca as Tags e os Fields (após pivot) no dicionário values
                resultados.append({
                    "timestamp": registo.get_time().isoformat(),
                    "device_id": registo.values.get("device_id"), # Tag
                    "type": registo.values.get("type"),           # Tag
                    "trigger": registo.values.get("trigger"),     # Tag
                    "lat": registo.values.get("lat"),             # Field
                    "lon": registo.values.get("lon")              # Field
                })
        return resultados
    except Exception as e:
        print(f" Erro ao ler do InfluxDB: {e}")
        return []
    
def get_recent_sensor_data(minutos: int):
    query = f"""
        from(bucket: "{settings.INFLUX_BUCKET}")
          |> range(start: -{minutos}m)
          |> filter(fn: (r) => r["_measurement"] == "Sensor")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    """
    
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
        print(f" Erro ao ler do InfluxDB: {e}")
        return []
    