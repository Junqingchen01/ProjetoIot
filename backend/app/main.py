from fastapi import FastAPI
from app.routers import telemetry, alerts
from dotenv import load_dotenv
import os

load_dotenv("../../.env")

app = FastAPI(title="IoT")

app.include_router(telemetry.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")

