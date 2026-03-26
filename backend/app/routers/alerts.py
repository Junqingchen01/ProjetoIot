from fastapi import APIRouter
from app.models.alert import AlertData       
from app.database import influx_db           
from app.core.security import validar_api_key
from fastapi import Depends

router = APIRouter()

@router.post("/alerts")
async def receive_alert_data(data: AlertData,   
api_key: str = Depends(validar_api_key)
):
    
    influx_db.save_alert_data(data)
    
    return {
        "status": "sucesso", 
     
    }
    
@router.get("/alerts")
async def fetch_alerts(minutos: int, api_key: str = Depends(validar_api_key)
):

    dados = influx_db.get_recent_alerts(minutos=minutos)
    
    return {
        "status": "sucesso",
        "total_registos": len(dados),
        "dados": dados
    }