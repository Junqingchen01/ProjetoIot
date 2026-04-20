import logging
from datetime import datetime, timezone
from app.models.sensor import SensorData
from app.models.alert import AlertData
from app.core.config import settings

logger = logging.getLogger(__name__)


device_states = {}

def create_alert(sensor: SensorData, event_type: str, trigger: str) -> AlertData:
    return AlertData(
        device_id=sensor.device_id,
        source=sensor.source,
        type="alert",
        event_type=event_type,
        timestamp=sensor.timestamp or datetime.now(timezone.utc),
        lat=sensor.lat,
        lon=sensor.lon,
        trigger=trigger,
        speed=sensor.speed,
        accel_x=sensor.accel_x,
        accel_y=sensor.accel_y,
        accel_z=sensor.accel_z
    )
    
def analyze_telemetry(data: SensorData) -> AlertData | None:
    
    if data.device_id not in device_states:
        device_states[data.device_id] = {
            "jam_start_time": None
        }
    state = device_states[data.device_id]
    
    max_accel = max([abs(data.accel_x), abs(data.accel_y), abs(data.accel_z)])
    
    if max_accel > settings.THRESHOLD_FALL_ACCEL:
        logger.warning(f"Queda detetada no dispositivo {data.device_id}!")
        return create_alert(data, "fall_accident", "accel_peak_exceeded")
    
    if data.accel_y < settings.THRESHOLD_HARD_BRAKE:
        logger.warning(f"Travagem brusca detetada no dispositivo {data.device_id}!")
        return create_alert(data, "hard_brake", "deceleration_threshold")

    if data.speed < settings.THRESHOLD_JAM_SPEED:
        if state["jam_start_time"] is None:
            state["jam_start_time"] = datetime.now(timezone.utc)
        else:
            duration = (datetime.now(timezone.utc) - state["jam_start_time"]).total_seconds()
            if duration > settings.JAM_TIME_WINDOW_SEC:
                state["jam_start_time"] = None
                logger.warning(f"Congestionamento detetado no dispositivo {data.device_id}!")
                return create_alert(data, "traffic_jam", "prolonged_low_speed")
    else:
        state["jam_start_time"] = None

    return None