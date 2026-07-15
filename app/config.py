from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Pokemon Cube Finder"
    database_url: str = "sqlite:///./pokemon_cube_finder.db"
    cubekoga_user_agent: str = "PokemonCubeFinder/0.1 (+local app)"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
