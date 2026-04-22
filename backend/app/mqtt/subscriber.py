import json
import logging
import paho.mqtt.client as mqtt
from app.core.config import settings
from app.database import influx_db
from app.models.sensor import SensorData
from app.models.alert import AlertData
import ssl
from app.services.websocket_manager import manager
import asyncio
import traceback

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

fastapi_loop = None

def on_connect(client,userdata,flags,rc):
    if rc == 0:
        print(f" Ligado ao broker MQTT em {settings.MQTT_BROKER}:{settings.MQTT_PORT} (TLS: {settings.MQTT_TLS_ENABLED})")  
        client.subscribe("/bike/+/telemetry",qos = 0)
        client.subscribe("/bike/+/alerts",qos=1)
        logger.info("A escutar")
    else:
        logger.info(f"Falha ao conectar ao mqtt: {rc}")    



def on_disconnect(client,userdata,rc):
    if rc!=0:
        logger.info("Desligado do mqtt")


def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode('utf-8') 
    
    try:
        data_dict = json.loads(payload)
        
        if topic.endswith("/telemetry"):
            from app.models.sensor import SensorData
            from app.services.detection import analyze_telemetry
            
            sensor_data = SensorData(**data_dict)
            influx_db.save_sensor_data(sensor_data)
            
            generated_alert = analyze_telemetry(sensor_data)
            
            if generated_alert:
                influx_db.save_alert_data(generated_alert)
                
                if fastapi_loop and fastapi_loop.is_running():
                    alert_json = generated_alert.model_dump(mode="json")
                    asyncio.run_coroutine_threadsafe(manager.broadcast_alert(alert_json), fastapi_loop)
                else:
                    logger.error("FastAPI loop não está disponível para WebSockets!")

        elif topic.endswith("/alert"):
            from app.models.alert import AlertData
            alert_data = AlertData(**data_dict)
            influx_db.save_alert_data(alert_data)
            
            if fastapi_loop and fastapi_loop.is_running():
                alert_json = alert_data.model_dump(mode="json")
                asyncio.run_coroutine_threadsafe(manager.broadcast_alert(alert_json), fastapi_loop)

    except json.JSONDecodeError:
        logger.error("Erro de Parsing: O JSON recebido não é válido.")
    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {e}")
        # Isto vai imprimir as linhas a vermelho no terminal dizendo exatamente ONDE falhou
        traceback.print_exc()   

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)

if settings.MQTT_USERNAME and settings.MQTT_PASSWORD:
    mqtt_client.username_pw_set(settings.MQTT_USERNAME,settings.MQTT_PASSWORD)

if settings.MQTT_TLS_ENABLED:
    mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED,tls_version=ssl.PROTOCOL_TLS) 

mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect= on_disconnect
mqtt_client.on_message = on_message


def start_mqtt(loop):
    global fastapi_loop
    fastapi_loop = loop
    try:
        mqtt_client.connect(settings.MQTT_BROKER, settings.MQTT_PORT, 60)
        mqtt_client.loop_start()
    except Exception as e:
        logger.error(f"Erro ao iniciar o mqtt {e}")


def stop_mqtt():
    mqtt_client.loop_stop()  # <- ALTERAR AQUI (substituir o ponto por um underscore)
    mqtt_client.disconnect()