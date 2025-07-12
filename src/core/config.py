from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    
    database_url: str = "sqlite:///./action_items.db"
    
    secret_key: str = "your-secret-key-here"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    
    faiss_index_path: str = "./data/faiss_index"
    terminology_db_path: str = "./data/terminology.db"
    
    upload_dir: str = "./uploads"
    processed_dir: str = "./processed"
    max_file_size: int = 524288000
    
    log_level: str = "INFO"
    log_file: str = "./logs/app.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()