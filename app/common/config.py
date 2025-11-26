from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Delta Trace OSINT CORE"
    debug: bool = True

    # JWT
    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expires_minutes: int = 15
    jwt_refresh_token_expires_days: int = 7

    # Banco (placeholder por enquanto)
    database_url: str = "postgresql+psycopg2://user:password@localhost:5432/deltatrace"


settings = Settings()
