from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class SensorData(BaseModel):
    device_id: str
    source: str        
    type: str   
    timestamp: Optional[datetime] = None
    lat: float        
    lon: float
    speed:float
    accel_x:float
    accel_y:float
    accel_z:float

    