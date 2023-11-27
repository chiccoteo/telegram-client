from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_id: int | None
    api_hash: str | None
    JWT_SECRET_KEY: str | None
    JWT_REFRESH_SECRET_KEY: str | None


settings = Settings()
