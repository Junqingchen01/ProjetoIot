from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    INFLUX_TOKEN: str
    INFLUX_ORG: str
    INFLUX_BUCKET: str = "Iot"
    API_KEY_EDGE: str
        
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

settings = Settings()