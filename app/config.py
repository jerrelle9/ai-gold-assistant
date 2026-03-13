from functools import lru_cache
from typing import List,Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    
    Application settings loaded from environment variables.
    pydantic-settings automatically reads from .env if present.

    """

    
    model_config=SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    #API 
    APP_ENV: str="development"
    APP_NAME: str = "AI Gold Trading Assistant"
    APP_VERSION: str="1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    #Database
    POSTGRES_HOST: str="localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str= "gold_trading"
    POSTGRES_USER: str="gold_user"
    POSTGRES_PASSWORD: Optional[str]=None
    DATABASE_URL: str = ""


    #API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: str = "http://localhost:3000, http://localhost:8501"

    #SECURITY
    SECRET_KEY: str="dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    #MARKET DATA APIs
    ALPHA_VANTAGE_API_KEY: str = ""
    POlYGON_API_KEY: str = ""
    TWELVE_DATA_API_KEY: str = ""

    #NEWS API
    NEWS_API_KEY: str = ""

    #OpenAI/LLM
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL:str="gpt-4o"


    # AWS
    AWS_ACCESS_KEY_ID:str=""
    AWS_SECRET_ACCESS_KEY:str=""
    AWS_REGION:str="us-east-1"
    S3_BUCKET_NAME:str=""


    #TRADNG SESSION CONFIG
    NY_SESSION_START: str="04:00"
    NY_SESSION_END:str="17:00"
    TIMEZONE:str="America/New_York"

    #Computed Properties
    # @field_validator("DATABASE_URL", mode="before")
    # @classmethod
    @model_validator(mode="after")
    def assemble_db_url(self) -> str:

        """Build DATABASE_URL from parts if not explicitly provided."""

        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql://{self.POSTGRES_USER}:"
                f"{self.POSTGRES_PASSWORD}@"
                f"{self.POSTGRES_HOST}:"
                f"{self.POSTGRES_PORT}/"
                f"{self.POSTGRES_DB}"
            )
        return self
    

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse comma-separated ALLOWED_ORIGINS into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
    
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"
    

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"
    


@lru_cache()
def get_settings() -> Settings:
    """
    Return a cached Settings instance.
    Using lru_cache means Settings is only instantiated once per process,
    making it safe and efficient to call get_settings() anywhere.
    """

    return Settings()


settings = get_settings()




