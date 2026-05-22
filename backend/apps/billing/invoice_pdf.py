# backend/apps/billing/invoice_pdf.py
# Feladat: Billing invoice PDF renderelést biztosít ReportLab segítségével. Tenant, issuer, buyer és invoice adatokból számla PDF bytes tartalmat és letöltési fájlnevet készít, HTML escape-pel védi a megjelenített szövegeket. Program-specifikus számla dokumentum renderer.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def money_label(cents: int) -> str:
    return f"{(int(cents or 0) / 100):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def render_invoice_pdf_document(
    *,
    tenant,
    invoice,
    issuer: dict[str, str],
    buyer: dict[str, str],
) -> tuple[bytes, str]:
    buyer_name = buyer.get("billing_company_name") or getattr(tenant, "name", None) or getattr(tenant, "slug", "")

    def html_lines(values: list[str]) -> str:
        return "<br/>".join(escape(str(value)) for value in values if str(value or "").strip())

    lines = [line for line in list(invoice.lines or []) if isinstance(line, dict)]
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("<b>FACTURA / SZÁMLA</b>", styles["Title"]))
    story.append(Spacer(1, 8))
    story.append(
        Table(
            [
                [
                    Paragraph(
                        "<b>Empresa Cliente</b><br/>"
                        + html_lines(
                            [
                                buyer_name,
                                f"NIF: {buyer.get('billing_tax_id')}" if buyer.get("billing_tax_id") else "",
                                buyer.get("billing_address_line", ""),
                                " ".join(filter(None, [buyer.get("billing_postal_code", ""), buyer.get("billing_city", "")])),
                                " | ".join(filter(None, [buyer.get("billing_region", ""), buyer.get("billing_country", "")])),
                            ]
                        ),
                        styles["Normal"],
                    ),
                    Paragraph(
                        "<b>" + escape(issuer["name"] or "BrainBankCenter") + "</b><br/>"
                        + html_lines(
                            [
                                issuer["tax_id"],
                                issuer["address_line"],
                                " ".join(filter(None, [issuer["postal_code"], issuer["city"]])),
                                " | ".join(filter(None, [issuer["region"], issuer["country"]])),
                            ]
                        ),
                        styles["Normal"],
                    ),
                ]
            ],
            colWidths=[85 * mm, 85 * mm],
        )
    )
    story.append(Spacer(1, 12))
    number = f"FRA{invoice.issued_at:%Y}/{int(invoice.id):06d}"
    story.append(Paragraph(f"<b>FACTURA {escape(number)}</b>", styles["Heading2"]))
    story.append(Paragraph(f"Fecha: {invoice.issued_at:%d/%m/%Y}", styles["Normal"]))
    contact = " | ".join(filter(None, [issuer["phone"], issuer["website"], issuer["email"]]))
    if contact:
        story.append(Paragraph(escape(contact), styles["Normal"]))
    story.append(Spacer(1, 12))
    table_rows = [["Descripción", "Cant.", "Precio Unit.", "IVA", "Total"]]
    net_total = int(round(int(invoice.total_cents or 0) / 1.27)) if int(invoice.total_cents or 0) > 0 else 0
    tax_total = int(invoice.total_cents or 0) - net_total
    for line in lines or [{"name": invoice.description, "quantity": 1, "total_cents": invoice.total_cents}]:
        quantity = int(line.get("quantity") or 1)
        gross = int(line.get("total_cents") or invoice.total_cents or 0)
        unit = int(line.get("unit_price_cents") or (gross // max(1, quantity)))
        table_rows.append(
            [
                str(line.get("name") or invoice.description or "Szolgáltatás"),
                f"{quantity},00",
                money_label(unit),
                "27%",
                money_label(gross),
            ]
        )
    table = Table(table_rows, colWidths=[78 * mm, 18 * mm, 28 * mm, 18 * mm, 28 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d0d0")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 14))
    story.append(Paragraph("Método de pago: Bankkártyás fizetés", styles["Normal"]))
    story.append(Paragraph("Mensaje: Fizetés rögzítve", styles["Normal"]))
    story.append(Spacer(1, 10))
    totals = Table(
        [
            ["Base Imp.", "% IVA", "IVA"],
            [money_label(net_total), "27 %", money_label(tax_total)],
            ["Subtotal", "", money_label(net_total)],
            ["Total IVA", "", money_label(tax_total)],
            ["Total", "", money_label(int(invoice.total_cents or 0))],
        ],
        colWidths=[90 * mm, 30 * mm, 50 * mm],
    )
    totals.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, 1), 0.4, colors.HexColor("#d0d0d0")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(totals)
    story.append(Spacer(1, 18))
    story.append(Paragraph("Página (1 / 1)", styles["Normal"]))
    doc.build(story)
    filename = f"szamla-{number.replace('/', '-')}.pdf"
    return buffer.getvalue(), filename


__all__ = ["money_label", "render_invoice_pdf_document"]
