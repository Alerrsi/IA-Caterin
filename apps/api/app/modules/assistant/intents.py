"""Carga y validación del catálogo de intenciones (intents.yaml, ADR-005)."""

import re
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from app.db.enums import DataDomain

CATALOG_PATH = Path(__file__).with_name("intents.yaml")
MIN_EXAMPLES = 8


class Intent(BaseModel):
    name: str
    description: str
    query: str
    domains: list[DataDomain]
    allow_level1: bool
    keywords: list[str]
    examples: list[str] = Field(min_length=MIN_EXAMPLES)
    template: str
    # Si la regla de esta intención y la de una de estas coinciden a la vez, gana esta (es más específica:
    # "¿qué lleva el pedido del sábado?" es order_detail aunque también diga "pedido").
    overrides: list[str] = []

    @field_validator("keywords")
    @classmethod
    def _valid_regex(cls, patterns: list[str]) -> list[str]:
        for p in patterns:
            re.compile(p)  # falla al cargar si una regex está mal escrita
        return patterns


class QuickAction(BaseModel):
    id: str
    label: str
    question: str
    intent: str


class Catalog(BaseModel):
    version: str
    intents: list[Intent]
    quick_actions: list[QuickAction] = []

    @model_validator(mode="after")
    def _consistent(self) -> "Catalog":
        names = [i.name for i in self.intents]
        if len(set(names)) != len(names):
            raise ValueError("Hay intenciones con el mismo nombre")
        for i in self.intents:
            unknown = set(i.overrides) - set(names)
            if unknown:
                raise ValueError(f"{i.name} tiene overrides que no existen: {sorted(unknown)}")
        for qa in self.quick_actions:
            if qa.intent not in names:
                raise ValueError(f"La acción rápida {qa.id} apunta a una intención que no existe: {qa.intent}")
        return self

    def by_name(self, name: str) -> Intent:
        return next(i for i in self.intents if i.name == name)


@lru_cache
def load_catalog(path: Path = CATALOG_PATH) -> Catalog:
    return Catalog.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
