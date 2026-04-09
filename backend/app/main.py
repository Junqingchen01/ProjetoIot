from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.routers import telemetry, alerts 
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from app.mqtt.subscriber import start_mqtt, stop_mqtt
from app.services.websocket_manager import manager  
import asyncio
import os

load_dotenv(".env")

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    start_mqtt(loop)
    yield
    stop_mqtt()

app = FastAPI(title="IoT", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/alerts")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

app.include_router(telemetry.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
