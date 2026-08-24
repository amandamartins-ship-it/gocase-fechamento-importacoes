from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://fechamento:fechamento@db:5432/fechamento_importacoes"

    jwt_secret_key: str = "troque-esta-chave-em-producao"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    admin_email: str = "amanda.martins@gocase.com"
    admin_password: str = "troque-esta-senha"

    # Google OAuth: suporta arquivo (desenvolvimento) ou JSON direto em variável de ambiente (produção)
    google_oauth_credentials_path: str = "/app/secrets/credentials.json"
    google_oauth_credentials_json: str | None = None  # JSON string do credentials (GoDeploy Secret)
    google_oauth_token_path: str = "/app/secrets/token.json"  # Deprecated: usar PostgreSQL em produção
    google_oauth_redirect_uri: str = "http://localhost:8000/drive/oauth/callback"  # Produção: usar Secret
    drive_importacoes_folder_name: str = "Importações"

    tolerancia_variacao_cambial: float = 0.02


@lru_cache
def get_settings() -> Settings:
    return Settings()
