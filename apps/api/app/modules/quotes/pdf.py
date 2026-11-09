"""PDF de la cotización para el cliente final (ReportLab, BSD).

Muestra productos, precios unitarios, subtotales, neto, IVA y total. Nunca muestra el costo de los
insumos ni el margen: eso es información interna de la pyme.
"""

import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.money import format_clp
from app.core.units import format_decimal
from app.db.models import Order, Pyme, Quote

TZ = ZoneInfo("America/Santiago")
BRAND = colors.HexColor("#9a3412")


def quote_number(quote: Quote) -> str:
    return f"COT-{str(quote.id)[:8].upper()}-v{quote.version}"


def _d(value: date | None) -> str:
    return value.strftime("%d-%m-%Y") if value else "—"


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_quote_pdf(quote: Quote, order: Order, pyme: Pyme) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Cotización {quote_number(quote)}",
        author=pyme.name,
        creator="Cáterin",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], alignment=0, textColor=BRAND, fontSize=20, spaceAfter=2)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#57534e"))
    normal = styles["Normal"]
    right = ParagraphStyle("right", parent=normal, alignment=TA_RIGHT)

    created = quote.created_at.astimezone(TZ) if isinstance(quote.created_at, datetime) else quote.created_at
    story: list[Any] = [
        Paragraph(_esc(pyme.name), h1),
        Paragraph(_esc(pyme.commune or ""), small),
        Spacer(1, 6 * mm),
        Paragraph(f"<b>Cotización {quote_number(quote)}</b>", styles["Heading2"]),
    ]
    info = [
        ["Fecha", created.strftime("%d-%m-%Y"), "Válida hasta", _d(quote.valid_until)],
        ["Cliente", _esc(order.customer_name), "Fecha del evento", _d(order.event_date)],
        ["Invitados", str(order.guests) if order.guests else "—", "", ""],
    ]
    info_table = Table(info, colWidths=[28 * mm, 60 * mm, 34 * mm, 52 * mm])
    info_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story += [info_table, Spacer(1, 6 * mm)]

    rows: list[list[Any]] = [["Producto", "Cantidad", "Precio unitario", "Subtotal"]]
    for p in quote.assumptions["products"]:
        qty = format_decimal(Decimal(p["qty"]))
        rows.append(
            [
                Paragraph(_esc(p["recipe_name"]), normal),
                f"{qty} {p['unit_label']}",
                format_clp(Decimal(p["unit_price_clp"])),
                format_clp(Decimal(p["subtotal_clp"])),
            ]
        )
    vat_label = f"IVA ({format_decimal(Decimal(quote.assumptions['vat_pct']))} %)"
    totals = [
        ["", "", "Neto", format_clp(quote.net_clp)],
        ["", "", vat_label, format_clp(quote.vat_clp)],
        ["", "", Paragraph("<b>Total</b>", right), Paragraph(f"<b>{format_clp(quote.total_clp)}</b>", right)],
    ]
    table = Table(rows + totals, colWidths=[78 * mm, 32 * mm, 34 * mm, 30 * mm], repeatRows=1)
    n = len(rows)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, n - 1), [colors.white, colors.HexColor("#fff7ed")]),
                ("LINEBELOW", (0, n - 1), (-1, n - 1), 0.5, colors.HexColor("#a8a29e")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story += [
        table,
        Spacer(1, 8 * mm),
        Paragraph("Valores en pesos chilenos (CLP). El total incluye IVA.", small),
    ]
    if order.notes:
        story += [Spacer(1, 3 * mm), Paragraph(f"Notas: {_esc(order.notes)}", small)]
    story += [Spacer(1, 10 * mm), Paragraph("Cotización generada con Cáterin.", small)]
    doc.build(story)
    return buf.getvalue()
