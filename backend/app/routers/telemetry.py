from fastapi import APIRouter
from app.models.sensor import SensorData       
from app.database import influx_db           
from app.core.security import validar_api_key
from fastapi import Depends

router = APIRouter()

@router.post("/sensors")
async def receive_alert_data(data: SensorData,
                             api_key: str = Depends(validar_api_key)
):
    
    influx_db.save_sensor_data(data)
    
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