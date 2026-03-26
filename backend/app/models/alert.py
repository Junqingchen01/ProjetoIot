from pydantic import BaseModel
from typing import Optional      
from datetime import datetime

class AlertData(BaseModel):
    device_id: str
    source: str        
    type: str   
    timestamp: Optional[datetime] = None
    lat: float        
    lon: float
    trigger: str
