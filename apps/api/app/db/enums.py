"""Enumeraciones del dominio (valores estables en inglés, se traducen en la interfaz)."""

from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    COLLABORATOR = "collaborator"
    CUSTOMER = "customer"  # cliente final de la pyme: solo usa el portal (ADR-007)


class BaseUnit(StrEnum):
    GRAM = "g"
    MILLILITER = "ml"
    UNIT = "unit"


class MovementReason(StrEnum):
    PURCHASE = "purchase"
    CONSUMPTION = "consumption"
    ADJUSTMENT = "adjustment"
    WASTE = "waste"
    PRODUCTION = "production"
    IMPORT = "import"


class PriceSourceKind(StrEnum):
    MANUAL = "manual"
    CSV = "csv"
    EXCEL = "excel"
    PRICE_LIST = "price_list"
    PRICE_SOURCE = "price_source"


class OrderStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    # Pedidos que arma un cliente en el portal (ADR-007):
    CUSTOMER_DRAFT = "customer_draft"  # cotizado por el cliente, sin enviar: la pyme no lo ve
    REQUESTED = "requested"  # enviado a la pyme, espera que la dueña lo acepte o rechace


class OrderSource(StrEnum):
    TEXT = "text"
    LIST = "list"
    FORM = "form"


class OrderUnit(StrEnum):
    UNIT = "unit"
    DOZEN = "dozen"
    GRAM = "g"
    KILOGRAM = "kg"
    MILLILITER = "ml"
    LITER = "l"
    PORTION = "portion"


class QuoteStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class IndexStatus(StrEnum):
    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"


class MetricKind(StrEnum):
    SURVEY = "survey"
    QUOTE_TIMING = "quote_timing"
    ASSISTANT_LATENCY = "assistant_latency"
    VISION_LATENCY = "vision_latency"
    MANUAL_BASELINE = "manual_baseline"


class CashKind(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


class DataDomain(StrEnum):
    INVENTORY = "inventory"
    RECIPES = "recipes"
    SUPPLIERS = "suppliers"
    ORDERS = "orders"
    CASH = "cash"
    DOCUMENTS = "documents"
    PRODUCTION = "production"
