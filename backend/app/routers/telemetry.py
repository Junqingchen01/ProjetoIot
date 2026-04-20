from fastapi import APIRouter
from app.models.sensor import SensorData       
from app.database import influx_db           
from app.core.security import validar_api_key
from app.services.detection import analyze_telemetry
from app.services.websocket_manager import manager
from fastapi import Depends
import asyncio

router = APIRouter()

@router.post("/sensors")
async def receive_alert_data(data: SensorData,
                             api_key: str = Depends(validar_api_key)
):
    
    influx_db.save_sensor_data(data)
    
    # Adicionar lógica de deteção para dados recebidos via API
    generated_alert = analyze_telemetry(data)
    if generated_alert:
        influx_db.save_alert_data(generated_alert)
        # Tentar enviar via WebSocket se possível
        try:
            alert_json = generated_alert.model_dump(mode="json")
            await manager.broadcast_alert(alert_json)
        except Exception:
            pass # Silencioso se falhar o broadcast
    
    return {
        "status": "sucesso", 
     
    }
    
@router.get("/sensors")
async def fetch_alerts(minutos: int, api_key: str = Depends(validar_api_key)
):

    dados = influx_db.get_recent_sensor_data(minutos=minutos)
    
    return {
        "status": "sucesso",
        "total_registos": len(dados),
        "dados": dados
    }