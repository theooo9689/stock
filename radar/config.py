from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator


class Settings(BaseModel):
    telegram_token: SecretStr = SecretStr("")
    telegram_chat: SecretStr = SecretStr("")
    openai_key: SecretStr = SecretStr("")
    fmp_key: SecretStr = SecretStr("")
    model: str = "gpt-4.1-mini"
    reasoning_effort: str = "medium"
    budget: float = Field(default=3, gt=0)
    input_price: float = Field(default=0.4, ge=0)
    output_price: float = Field(default=1.6, ge=0)
    search_price: float = Field(default=0.01, ge=0)
    max_output_tokens: int = Field(default=12000, ge=1000, le=32000)
    max_tool_calls: int = Field(default=6, ge=1, le=20)
    background: bool = False
    data_dir: Path = Path("data")
    reports_dir: Path = Path("reports")
    config_path: Path = Path("config/watchlist.yaml")
    timezone: str = "America/Sao_Paulo"
    delivery_time: str = "20:30"

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        ZoneInfo(value)
        return value

    @field_validator("reasoning_effort")
    @classmethod
    def valid_reasoning(cls, value):
        if value not in ("none", "low", "medium", "high", "xhigh"):
            raise ValueError("Esforço de raciocínio inválido")
        return value

    @field_validator("delivery_time")
    @classmethod
    def valid_time(cls, value):
        datetime.strptime(value, "%H:%M")
        return value

    @classmethod
    def from_env(cls):
        load_dotenv(override=False)
        names = {
            "telegram_token": "TELEGRAM_BOT_TOKEN", "telegram_chat": "TELEGRAM_CHAT_ID",
            "openai_key": "OPENAI_API_KEY", "fmp_key": "FMP_API_KEY", "model": "OPENAI_MODEL",
            "budget": "DAILY_BUDGET_USD", "input_price": "MODEL_INPUT_USD_PER_MILLION",
            "output_price": "MODEL_OUTPUT_USD_PER_MILLION", "search_price": "WEB_SEARCH_USD_PER_CALL",
            "max_output_tokens": "RESEARCH_MAX_OUTPUT_TOKENS", "max_tool_calls": "RESEARCH_MAX_TOOL_CALLS",
            "background": "RESEARCH_BACKGROUND", "data_dir": "RADAR_DATA_DIR",
            "reasoning_effort": "OPENAI_REASONING_EFFORT",
            "reports_dir": "RADAR_REPORTS_DIR", "config_path": "RADAR_CONFIG",
            "timezone": "RADAR_TIMEZONE", "delivery_time": "RADAR_DELIVERY_TIME",
        }
        result = cls(**{k: os.environ[v] for k, v in names.items() if v in os.environ})
        result.data_dir.mkdir(parents=True, exist_ok=True)
        result.reports_dir.mkdir(parents=True, exist_ok=True)
        return result

    def now(self):
        return datetime.now(ZoneInfo(self.timezone))


class Watchlist(BaseModel):
    assets: dict
    market_symbols: dict[str, str] = Field(default_factory=dict)
    discovery: dict
    weights: dict[str, dict[str, float]]
    valuation: dict
    news_feeds: list[str]

    @model_validator(mode="after")
    def validate_weights(self):
        for kind, weights in self.weights.items():
            if any(v < 0 for v in weights.values()) or abs(sum(weights.values()) - 1) > 1e-8:
                raise ValueError(f"Pesos inválidos: {kind}")
        return self

    @classmethod
    def load(cls, path):
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))

    def instruments(self):
        result = []
        for category in ("us_etfs", "br_etfs", "stocks", "crypto"):
            for symbol in self.assets.get(category, []):
                result.append({"symbol": symbol, "category": category, "watchlist": True})
        return result
