"""Generate the validated Finance Excel workbook in memory."""

from __future__ import annotations

import io
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .models import InvoiceAnalysis, InvoiceLine

BLUE = "00A9E0"
MIDNIGHT = "00153D"
WHITE = "FFFFFF"
LIGHT_BLUE = "DDF4FC"
THIN = Side(style="thin", color="D9E2EA")


def build_excel(analysis: InvoiceAnalysis, lines: list[InvoiceLine]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Detalle"
    sheet.sheet_view.showGridLines = False

    sheet.merge_cells("A1:I1")
    title = sheet["A1"]
    title.value = "SERVICIOS CERTIFICADOS"
    title.fill = PatternFill("solid", fgColor=BLUE)
    title.font = Font(color=WHITE, bold=True, size=12)
    title.alignment = Alignment(horizontal="center")

    metadata = [
        ("Proveedor", analysis.provider),
        ("Factura", analysis.invoice_number),
        ("Fecha", analysis.invoice_date),
        ("Cliente", analysis.customer_name),
    ]
    for row_index, (label, value) in enumerate(metadata, start=3):
        sheet.cell(row=row_index, column=1, value=label).font = Font(bold=True, color=MIDNIGHT)
        sheet.merge_cells(start_row=row_index, start_column=2, end_row=row_index, end_column=4)
        sheet.cell(row=row_index, column=2, value=value)

    header_row = 8
    headers = [
        "FECHA",
        "USUARIO",
        "REFERENCIA PROYECTO",
        "SERVICIO",
        "CANTIDAD",
        "PRECIO UNITARIO",
        "IMPORTE",
        "ESTADO",
        "COMENTARIOS",
    ]
    for column, value in enumerate(headers, start=1):
        cell = sheet.cell(row=header_row, column=column, value=value)
        cell.fill = PatternFill("solid", fgColor=BLUE)
        cell.font = Font(color=WHITE, bold=True)
        cell.alignment = Alignment(horizontal="center")

    for row_index, line in enumerate(lines, start=header_row + 1):
        values: list[object] = [
            analysis.invoice_date,
            line.user,
            line.project_reference,
            line.service,
            float(line.quantity),
            float(line.unit_price),
            float(line.amount),
            "Validada",
            line.comment,
        ]
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row=row_index, column=column, value=value)
            cell.border = Border(bottom=THIN)
        sheet.cell(row=row_index, column=5).number_format = "#,##0.00"
        sheet.cell(row=row_index, column=6).number_format = '#,##0.0000 "€"'
        sheet.cell(row=row_index, column=7).number_format = '#,##0.00 "€"'

    total_row = header_row + len(lines) + 2
    sheet.cell(row=total_row, column=6, value="Total validado").font = Font(bold=True, color=MIDNIGHT)
    total_cell = sheet.cell(
        row=total_row,
        column=7,
        value=float(sum((line.amount for line in lines), start=Decimal("0"))),
    )
    total_cell.fill = PatternFill("solid", fgColor=LIGHT_BLUE)
    total_cell.font = Font(bold=True, color=MIDNIGHT)
    total_cell.number_format = '#,##0.00 "€"'

    widths = [13, 24, 22, 35, 13, 18, 14, 13, 42]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = f"A{header_row + 1}"
    sheet.auto_filter.ref = f"A{header_row}:I{header_row + len(lines)}"

    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()

