"""Modelos SQLAlchemy de Cáterin. Referencia: docs/DATA_MODEL.md.

Un solo archivo para que Alembic vea todo el esquema y las relaciones se lean de una vez.
Las reglas de negocio no viven aquí: están en los `service.py` de cada módulo.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Money, Percent, Quantity, TenantMixin, TimestampMixin, str_enum, tenant_args
from app.db.enums import (
    BaseUnit,
    CashKind,
    DataDomain,
    IndexStatus,
    MetricKind,
    MovementReason,
    OrderSource,
    OrderStatus,
    OrderUnit,
    PriceSourceKind,
    QuoteStatus,
    Role,
)

EMBEDDING_DIM = 1024  # BAAI/bge-m3 (ADR-003). Cambiarlo exige migración y reindexación.


# --------------------------------------------------------------------------- pyme y usuarias


class Pyme(TimestampMixin, Base):
    __tablename__ = "pyme"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    rut: Mapped[str | None] = mapped_column(String(12))
    commune: Mapped[str | None] = mapped_column(String(80))
    default_waste_pct: Mapped[Decimal] = mapped_column(Percent, server_default="0")
    default_margin_pct: Mapped[Decimal | None] = mapped_column(Percent)
    vat_pct: Mapped[Decimal] = mapped_column(Percent, server_default="19.00")
    prices_include_vat: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("true"))
    quote_validity_days: Mapped[int | None] = mapped_column(SmallInteger)
    is_demo: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
    # Código del enlace para que los clientes se registren en el portal (ADR-007). None = portal cerrado.
    customer_code: Mapped[str | None] = mapped_column(String(32), unique=True)

    __table_args__ = (
        CheckConstraint("default_waste_pct >= 0 AND default_waste_pct < 100", name="waste_range"),
        CheckConstraint("default_margin_pct IS NULL OR default_margin_pct >= 0", name="margin_positive"),
        CheckConstraint("vat_pct >= 0 AND vat_pct < 100", name="vat_range"),
    )


class User(TenantMixin, Base):
    __tablename__ = "app_user"

    email: Mapped[str] = mapped_column(CITEXT)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(str_enum(Role, "role"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("true"))

    # El correo del equipo es único en todo el sistema. Un cliente del portal (ADR-007) tiene una cuenta por cada pyme
    # a la que cotiza, con el mismo correo: única por pyme.
    __table_args__ = tenant_args(
        "app_user",
        extra=(
            UniqueConstraint("pyme_id", "email", name="uq_app_user_pyme_email"),
            Index("uq_app_user_staff_email", "email", unique=True, postgresql_where=sql_text("role <> 'customer'")),
        ),
    )


class RefreshToken(TenantMixin, Base):
    """Refresh tokens rotados; se guarda solo el hash (docs/SECURITY.md)."""

    __tablename__ = "refresh_token"

    user_id: Mapped[uuid.UUID] = mapped_column()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = tenant_args("refresh_token", ("user_id", "app_user", "CASCADE"))


class LoginAttempt(Base):
    """Intentos fallidos de login para limitar la fuerza bruta. Sin tenant: ocurre antes de saber la pyme."""

    __tablename__ = "login_attempt"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(CITEXT, index=True)
    ip: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


# --------------------------------------------------------------------------- inventario


class Ingredient(TenantMixin, Base):
    __tablename__ = "ingredient"

    name: Mapped[str] = mapped_column(String(120))
    base_unit: Mapped[BaseUnit] = mapped_column(str_enum(BaseUnit, "base_unit"))
    stock_qty: Mapped[Decimal] = mapped_column(Quantity, server_default="0")
    min_stock_qty: Mapped[Decimal | None] = mapped_column(Quantity)
    waste_pct: Mapped[Decimal | None] = mapped_column(Percent)
    density_g_per_ml: Mapped[Decimal | None] = mapped_column(Quantity)
    category: Mapped[str | None] = mapped_column(String(60))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("true"))
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(index=True)

    __table_args__ = tenant_args(
        "ingredient",
        extra=(
            Index("uq_ingredient_pyme_name", "pyme_id", func.lower(sql_text("name")), unique=True),
            CheckConstraint("waste_pct IS NULL OR (waste_pct >= 0 AND waste_pct < 100)", name="waste_range"),
            CheckConstraint("density_g_per_ml IS NULL OR density_g_per_ml > 0", name="density_positive"),
        ),
    )


class StockMovement(TenantMixin, Base):
    """Libro de movimientos de stock: solo crece; es la fuente de verdad (ADR-004)."""

    __tablename__ = "stock_movement"

    ingredient_id: Mapped[uuid.UUID] = mapped_column()
    delta_qty: Mapped[Decimal] = mapped_column(Quantity)
    reason: Mapped[MovementReason] = mapped_column(str_enum(MovementReason, "movement_reason"))
    note: Mapped[str | None] = mapped_column(String(200))
    reference_type: Mapped[str | None] = mapped_column(String(40))
    reference_id: Mapped[uuid.UUID | None] = mapped_column()
    client_op_id: Mapped[uuid.UUID | None] = mapped_column()
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = tenant_args(
        "stock_movement",
        ("ingredient_id", "ingredient", "CASCADE"),
        extra=(UniqueConstraint("pyme_id", "client_op_id", name="uq_stock_movement_client_op"),),
    )


# --------------------------------------------------------------------------- proveedores y precios


class Supplier(TenantMixin, Base):
    __tablename__ = "supplier"

    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(120))
    website: Mapped[str | None] = mapped_column(String(200))
    delivery_days: Mapped[list[int] | None] = mapped_column(ARRAY(SmallInteger))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("true"))

    __table_args__ = tenant_args(
        "supplier",
        extra=(Index("uq_supplier_pyme_name", "pyme_id", func.lower(sql_text("name")), unique=True),),
    )


class IngredientPrice(TenantMixin, Base):
    """Precio de una presentación. No se edita: un cambio crea una versión nueva."""

    __tablename__ = "ingredient_price"

    ingredient_id: Mapped[uuid.UUID] = mapped_column()
    supplier_id: Mapped[uuid.UUID] = mapped_column()
    package_label: Mapped[str] = mapped_column(String(80))
    package_qty: Mapped[Decimal] = mapped_column(Quantity)
    price_clp: Mapped[Decimal] = mapped_column(Money)
    includes_vat: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("true"))
    price_date: Mapped[date] = mapped_column(Date)
    source: Mapped[PriceSourceKind] = mapped_column(str_enum(PriceSourceKind, "price_source_kind"))
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("true"))

    supplier: Mapped["Supplier"] = relationship(
        primaryjoin="and_(IngredientPrice.supplier_id == Supplier.id, IngredientPrice.pyme_id == Supplier.pyme_id)",
        foreign_keys="[IngredientPrice.supplier_id, IngredientPrice.pyme_id]",
        viewonly=True,
        lazy="raise",
    )

    __table_args__ = tenant_args(
        "ingredient_price",
        ("ingredient_id", "ingredient", "CASCADE"),
        ("supplier_id", "supplier", "CASCADE"),
        extra=(
            Index(
                "uq_ingredient_price_current",
                "pyme_id",
                "ingredient_id",
                "supplier_id",
                "package_label",
                unique=True,
                postgresql_where=sql_text("is_current"),
            ),
            CheckConstraint("package_qty > 0", name="package_qty_positive"),
            CheckConstraint("price_clp >= 0", name="price_positive"),
        ),
    )


# --------------------------------------------------------------------------- recetas


class Recipe(TenantMixin, Base):
    __tablename__ = "recipe"

    name: Mapped[str] = mapped_column(String(120))
    yield_qty: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    yield_unit: Mapped[BaseUnit] = mapped_column(str_enum(BaseUnit, "yield_unit"))
    is_final_product: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("true"))
    vision_class: Mapped[str | None] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("true"))

    lines: Mapped[list["RecipeLine"]] = relationship(
        primaryjoin="and_(Recipe.id == RecipeLine.recipe_id, Recipe.pyme_id == RecipeLine.pyme_id)",
        foreign_keys="[RecipeLine.recipe_id, RecipeLine.pyme_id]",
        cascade="all, delete-orphan",
        order_by="RecipeLine.created_at",
        overlaps="lines",
    )

    __table_args__ = tenant_args(
        "recipe",
        extra=(
            Index("uq_recipe_pyme_name", "pyme_id", func.lower(sql_text("name")), unique=True),
            Index(
                "uq_recipe_pyme_vision_class",
                "pyme_id",
                "vision_class",
                unique=True,
                postgresql_where=sql_text("vision_class IS NOT NULL"),
            ),
            CheckConstraint("yield_qty > 0", name="yield_positive"),
        ),
    )


class RecipeLine(TenantMixin, Base):
    __tablename__ = "recipe_line"

    recipe_id: Mapped[uuid.UUID] = mapped_column()
    ingredient_id: Mapped[uuid.UUID] = mapped_column()
    qty: Mapped[Decimal] = mapped_column(Quantity)
    waste_pct: Mapped[Decimal | None] = mapped_column(Percent)

    __table_args__ = tenant_args(
        "recipe_line",
        ("recipe_id", "recipe", "CASCADE"),
        ("ingredient_id", "ingredient", "RESTRICT"),
        extra=(
            UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_line_ingredient"),
            CheckConstraint("qty > 0", name="qty_positive"),
            CheckConstraint("waste_pct IS NULL OR (waste_pct >= 0 AND waste_pct < 100)", name="waste_range"),
        ),
    )


# --------------------------------------------------------------------------- pedidos y cotizaciones


class Order(TenantMixin, Base):
    __tablename__ = "catering_order"

    customer_name: Mapped[str] = mapped_column(String(120))
    customer_contact: Mapped[str | None] = mapped_column(String(120))
    event_date: Mapped[date | None] = mapped_column(Date)
    guests: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[OrderStatus] = mapped_column(str_enum(OrderStatus, "order_status"))
    source: Mapped[OrderSource] = mapped_column(str_enum(OrderSource, "order_source"))
    raw_text: Mapped[str | None] = mapped_column(Text)
    extraction: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    # Portal de clientes (ADR-007): quién lo pidió, cuándo lo envió y la respuesta de la pyme.
    customer_user_id: Mapped[uuid.UUID | None] = mapped_column()
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner_message: Mapped[str | None] = mapped_column(Text)

    lines: Mapped[list["OrderLine"]] = relationship(
        primaryjoin="and_(Order.id == OrderLine.order_id, Order.pyme_id == OrderLine.pyme_id)",
        foreign_keys="[OrderLine.order_id, OrderLine.pyme_id]",
        cascade="all, delete-orphan",
        order_by="OrderLine.position",
        overlaps="lines",
    )

    __table_args__ = tenant_args(
        "catering_order",
        ("customer_user_id", "app_user", None),
        extra=(
            CheckConstraint("guests IS NULL OR guests > 0", name="guests_positive"),
            Index("ix_catering_order_pyme_event", "pyme_id", "event_date"),
            Index(
                "ix_catering_order_customer",
                "pyme_id",
                "customer_user_id",
                postgresql_where=sql_text("customer_user_id IS NOT NULL"),
            ),
        ),
    )


class OrderLine(TenantMixin, Base):
    __tablename__ = "order_line"

    order_id: Mapped[uuid.UUID] = mapped_column()
    recipe_id: Mapped[uuid.UUID | None] = mapped_column()
    position: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    requested_name: Mapped[str] = mapped_column(String(160))
    qty: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    unit: Mapped[OrderUnit] = mapped_column(str_enum(OrderUnit, "order_unit"))

    __table_args__ = tenant_args(
        "order_line",
        ("order_id", "catering_order", "CASCADE"),
        ("recipe_id", "recipe", "RESTRICT"),
        extra=(CheckConstraint("qty > 0", name="qty_positive"),),
    )


class Quote(TenantMixin, Base):
    __tablename__ = "quote"

    order_id: Mapped[uuid.UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[QuoteStatus] = mapped_column(str_enum(QuoteStatus, "quote_status"))
    price_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    assumptions: Mapped[dict[str, Any]] = mapped_column(JSONB)
    ingredients_cost_clp: Mapped[Decimal] = mapped_column(Money)
    margin_pct: Mapped[Decimal] = mapped_column(Percent)
    net_clp: Mapped[Decimal] = mapped_column(Money)
    vat_clp: Mapped[Decimal] = mapped_column(Money)
    total_clp: Mapped[Decimal] = mapped_column(Money)
    is_complete: Mapped[bool] = mapped_column(Boolean)
    pdf_path: Mapped[str | None] = mapped_column(String(255))
    calc_version: Mapped[str] = mapped_column(String(20))
    valid_until: Mapped[date | None] = mapped_column(Date)

    lines: Mapped[list["QuoteLine"]] = relationship(
        primaryjoin="and_(Quote.id == QuoteLine.quote_id, Quote.pyme_id == QuoteLine.pyme_id)",
        foreign_keys="[QuoteLine.quote_id, QuoteLine.pyme_id]",
        cascade="all, delete-orphan",
        order_by="QuoteLine.position",
        overlaps="lines",
    )

    __table_args__ = tenant_args(
        "quote",
        ("order_id", "catering_order", "CASCADE"),
        extra=(UniqueConstraint("order_id", "version", name="uq_quote_order_version"),),
    )


class QuoteLine(TenantMixin, Base):
    __tablename__ = "quote_line"

    quote_id: Mapped[uuid.UUID] = mapped_column()
    ingredient_id: Mapped[uuid.UUID] = mapped_column()
    position: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    required_qty: Mapped[Decimal] = mapped_column(Quantity)
    stock_used_qty: Mapped[Decimal] = mapped_column(Quantity)
    to_buy_qty: Mapped[Decimal] = mapped_column(Quantity)
    ingredient_price_id: Mapped[uuid.UUID | None] = mapped_column()
    supplier_id: Mapped[uuid.UUID | None] = mapped_column()
    packages_to_buy: Mapped[int] = mapped_column(Integer)
    unit_price_clp: Mapped[Decimal | None] = mapped_column(Money)
    subtotal_clp: Mapped[Decimal] = mapped_column(Money)
    price_date: Mapped[date | None] = mapped_column(Date)
    alternatives: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=sql_text("'[]'::jsonb"))
    note: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = tenant_args(
        "quote_line",
        ("quote_id", "quote", "CASCADE"),
        ("ingredient_id", "ingredient", "RESTRICT"),
        ("ingredient_price_id", "ingredient_price", "RESTRICT"),
        ("supplier_id", "supplier", "RESTRICT"),
    )


# --------------------------------------------------------------------------- producción (F2)


class ProductionRecord(TenantMixin, Base):
    __tablename__ = "production_record"

    recipe_id: Mapped[uuid.UUID] = mapped_column()
    detected_qty: Mapped[int | None] = mapped_column(Integer)
    confirmed_qty: Mapped[int] = mapped_column(Integer)
    image_path: Mapped[str | None] = mapped_column(String(255))
    model_version: Mapped[str | None] = mapped_column(String(60))
    detections: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    was_corrected: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
    client_op_id: Mapped[uuid.UUID | None] = mapped_column()

    __table_args__ = tenant_args(
        "production_record",
        ("recipe_id", "recipe", "RESTRICT"),
        extra=(
            UniqueConstraint("pyme_id", "client_op_id", name="uq_production_record_client_op"),
            CheckConstraint("confirmed_qty >= 0", name="confirmed_positive"),
        ),
    )


# --------------------------------------------------------------------------- documentos y RAG (F1)


class Document(TenantMixin, Base):
    __tablename__ = "document"

    filename: Mapped[str] = mapped_column(String(200))
    mime_type: Mapped[str] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(255))
    index_status: Mapped[IndexStatus] = mapped_column(str_enum(IndexStatus, "index_status"))

    __table_args__ = tenant_args(
        "document", extra=(UniqueConstraint("pyme_id", "sha256", name="uq_document_pyme_sha256"),)
    )


class DocumentChunk(TenantMixin, Base):
    __tablename__ = "document_chunk"

    document_id: Mapped[uuid.UUID] = mapped_column()
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    # Sin tildes en ambos lados: "minimo" encuentra "mínimo" (migración a1bfdccff932).
    tsv: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('spanish', caterin_unaccent(text))", persisted=True)
    )
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(80))
    embedding_version: Mapped[str] = mapped_column(String(40))
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sql_text("'{}'::jsonb"))

    __table_args__ = tenant_args(
        "document_chunk",
        ("document_id", "document", "CASCADE"),
        extra=(
            Index("ix_document_chunk_tsv", "tsv", postgresql_using="gin"),
            Index(
                "ix_document_chunk_embedding",
                "embedding",
                postgresql_using="hnsw",
                postgresql_with={"m": 16, "ef_construction": 64},
                postgresql_ops={"embedding": "vector_cosine_ops"},
            ),
        ),
    )


# --------------------------------------------------------------------------- fichas del negocio (ADR-006)


class KnowledgeCard(TenantMixin, Base):
    """Ficha de texto de un insumo, receta, proveedor o pedido, generada por código, para el RAG (ADR-006).

    No es fuente de verdad: se regenera desde las tablas de negocio cuando cambia su `data_version`."""

    __tablename__ = "knowledge_card"

    kind: Mapped[str] = mapped_column(String(20))  # ingredient | recipe | supplier | order
    entity_id: Mapped[uuid.UUID] = mapped_column()
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    text_hash: Mapped[str] = mapped_column(String(64))
    tsv: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('spanish', caterin_unaccent(text))", persisted=True)
    )
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(80))
    embedding_version: Mapped[str] = mapped_column(String(40))

    __table_args__ = tenant_args(
        "knowledge_card",
        extra=(
            UniqueConstraint("pyme_id", "kind", "entity_id", name="uq_knowledge_card_entity"),
            CheckConstraint("kind IN ('ingredient', 'recipe', 'supplier', 'order')", name="kind_valid"),
            Index("ix_knowledge_card_tsv", "tsv", postgresql_using="gin"),
            Index(
                "ix_knowledge_card_embedding",
                "embedding",
                postgresql_using="hnsw",
                postgresql_with={"m": 16, "ef_construction": 64},
                postgresql_ops={"embedding": "vector_cosine_ops"},
            ),
        ),
    )


class KnowledgeSync(TenantMixin, Base):
    """Hasta qué `data_version` de cada dominio están al día las fichas de la pyme."""

    __tablename__ = "knowledge_sync"

    domain: Mapped[DataDomain] = mapped_column(str_enum(DataDomain, "knowledge_sync_domain"))
    version: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = tenant_args(
        "knowledge_sync", extra=(UniqueConstraint("pyme_id", "domain", name="uq_knowledge_sync_domain"),)
    )


# --------------------------------------------------------------------------- asistente y métricas


class AssistantInteraction(TenantMixin, Base):
    __tablename__ = "assistant_interaction"

    user_id: Mapped[uuid.UUID] = mapped_column()
    question: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(60))
    level: Mapped[int] = mapped_column(SmallInteger)
    router_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    entities: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sql_text("'{}'::jsonb"))
    queries: Mapped[list[Any]] = mapped_column(JSONB, server_default=sql_text("'[]'::jsonb"))
    sources: Mapped[list[Any]] = mapped_column(JSONB, server_default=sql_text("'[]'::jsonb"))
    cache_hit: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
    fallback_reason: Mapped[str | None] = mapped_column(String(40))
    llm_model: Mapped[str | None] = mapped_column(String(60))
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    first_token_ms: Mapped[int | None] = mapped_column(Integer)
    intents_version: Mapped[str | None] = mapped_column(String(20))
    feedback: Mapped[int | None] = mapped_column(SmallInteger)  # 1 = útil, -1 = no útil (la usuaria)

    __table_args__ = tenant_args(
        "assistant_interaction",
        ("user_id", "app_user", "CASCADE"),
        extra=(
            Index("ix_assistant_interaction_pyme_created", "pyme_id", "created_at"),
            CheckConstraint("feedback IS NULL OR feedback IN (-1, 1)", name="feedback_range"),
        ),
    )


class MetricEvent(TenantMixin, Base):
    __tablename__ = "metric_event"

    user_id: Mapped[uuid.UUID | None] = mapped_column()
    kind: Mapped[MetricKind] = mapped_column(str_enum(MetricKind, "metric_kind"))
    value_num: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sql_text("'{}'::jsonb"))

    __table_args__ = tenant_args(
        "metric_event",
        ("user_id", "app_user", "CASCADE"),
        extra=(Index("ix_metric_event_pyme_kind_created", "pyme_id", "kind", "created_at"),),
    )


# --------------------------------------------------------------------------- caja (propuesta)


class CashMovement(TenantMixin, Base):
    __tablename__ = "cash_movement"

    kind: Mapped[CashKind] = mapped_column(str_enum(CashKind, "cash_kind"))
    amount_clp: Mapped[Decimal] = mapped_column(Money)
    category: Mapped[str] = mapped_column(String(60))
    occurred_on: Mapped[date] = mapped_column(Date)
    reference_type: Mapped[str | None] = mapped_column(String(40))
    reference_id: Mapped[uuid.UUID | None] = mapped_column()

    __table_args__ = tenant_args("cash_movement", extra=(CheckConstraint("amount_clp > 0", name="amount_positive"),))


# --------------------------------------------------------------------------- sistema


class DataVersion(Base):
    """Versión de datos por pyme y dominio; invalida la caché del asistente (ADR-005)."""

    __tablename__ = "data_version"

    pyme_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    domain: Mapped[DataDomain] = mapped_column(str_enum(DataDomain, "data_domain"), primary_key=True)
    version: Mapped[int] = mapped_column(BigInteger, server_default="0")

    __table_args__ = (ForeignKeyConstraint(["pyme_id"], ["pyme.id"], ondelete="CASCADE"),)
