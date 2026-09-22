from functools import lru_cache
import os

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    class Settings(BaseSettings):
        model_config = SettingsConfigDict(env_file=".env", extra="ignore")

        app_name: str = "BharatRisk AI"
        environment: str = "demo"
        supabase_url: str = ""
        supabase_key: str = ""
        supabase_service_role_key: str = ""
        api_token: str = "demo-authority-token"
        cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
        copernicus_client_id: str = ""
        copernicus_client_secret: str = ""
        copernicus_username: str = ""
        copernicus_password: str = ""
        copernicus_token_url: str = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
        copernicus_catalog_url: str = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
        copernicus_process_url: str = "https://sh.dataspace.copernicus.eu/api/v1/process"
        imdaa_data_dir: str = "data/imdaa"
        insat_data_dir: str = "data/insat"
        dem_data_dir: str = "data/dem"
        ingestion_interval_minutes: int = 15
        alert_webhook_url: str = ""
        alert_webhook_token: str = ""
        alert_sms_webhook_url: str = ""

        @property
        def cors_list(self) -> list[str]:
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
except ImportError:
    class Settings:
        def __init__(self):
            self.app_name = os.getenv("APP_NAME", "BharatRisk AI")
            self.environment = os.getenv("ENVIRONMENT", "demo")
            self.supabase_url = os.getenv("SUPABASE_URL", "")
            self.supabase_key = os.getenv("SUPABASE_KEY", "")
            self.supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
            self.api_token = os.getenv("API_TOKEN", "demo-authority-token")
            self.cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
            self.copernicus_client_id = os.getenv("COPERNICUS_CLIENT_ID", "")
            self.copernicus_client_secret = os.getenv("COPERNICUS_CLIENT_SECRET", "")
            self.copernicus_username = os.getenv("COPERNICUS_USERNAME", "")
            self.copernicus_password = os.getenv("COPERNICUS_PASSWORD", "")
            self.copernicus_token_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
            self.copernicus_catalog_url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
            self.copernicus_process_url = "https://sh.dataspace.copernicus.eu/api/v1/process"
            self.imdaa_data_dir = os.getenv("IMDAA_DATA_DIR", "data/imdaa")
            self.insat_data_dir = os.getenv("INSAT_DATA_DIR", "data/insat")
            self.dem_data_dir = os.getenv("DEM_DATA_DIR", "data/dem")
            self.ingestion_interval_minutes = int(os.getenv("INGESTION_INTERVAL_MINUTES", "15"))
            self.alert_webhook_url = os.getenv("ALERT_WEBHOOK_URL", "")
            self.alert_webhook_token = os.getenv("ALERT_WEBHOOK_TOKEN", "")
            self.alert_sms_webhook_url = os.getenv("ALERT_SMS_WEBHOOK_URL", "")

        @property
        def cors_list(self) -> list[str]:
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

