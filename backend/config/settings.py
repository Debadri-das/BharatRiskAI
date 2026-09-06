from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "BharatRisk AI"
    environment: str = "demo"
    database_url: str = "sqlite:///./bharatrisk.db"
    api_token: str = "demo-authority-token"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    copernicus_client_id: str = ""
    copernicus_client_secret: str = ""
    copernicus_username: str = ""
    copernicus_password: str = ""
    copernicus_token_url: str = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    copernicus_catalog_url: str = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
    copernicus_process_url: str = "https://sh.dataspace.copernicus.eu/api/v1/process"

    @property
    def cors_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
