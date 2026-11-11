from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .servicios_demo import pesos


fuentes = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("BuildCorp", str(fuentes / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("BuildCorpBold", str(fuentes / "VeraBd.ttf")))


def generar_documento(solicitud, tipo):
    salida = BytesIO()
    documento = SimpleDocTemplate(
        salida, pagesize=(210 * mm, 297 * mm), rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=22 * mm,
        title=f"BuildCorp {solicitud.numero_documento}", author="BuildCorp",
    )
    normal = ParagraphStyle("normal", fontName="BuildCorp", fontSize=9, leading=13, textColor=colors.HexColor("#30232c"))
    titulo = ParagraphStyle("titulo", parent=normal, fontName="BuildCorpBold", fontSize=19, leading=24)
    subtitulo = ParagraphStyle("subtitulo", parent=normal, fontName="BuildCorpBold", fontSize=11, leading=16, spaceBefore=12, spaceAfter=5)
    importe = ParagraphStyle("importe", parent=normal, alignment=TA_RIGHT)

    def texto(valor, estilo=normal):
        return Paragraph(escape(str(valor)).replace("\n", "<br/>"), estilo)

    def tabla(filas, anchos):
        resultado = Table([[texto(celda) for celda in fila] for fila in filas], colWidths=anchos, hAlign="LEFT")
        resultado.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("LINEBELOW", (0, 0), (-1, -1), .4, colors.HexColor("#eddae4")),
        ]))
        return resultado

    logo = Path(settings.BASE_DIR) / "inventario/static/buildcorp/logo-gato-casco.png"
    encabezado = Table([
        [Image(str(logo), width=16 * mm, height=16 * mm), texto("BuildCorp", titulo)],
    ], colWidths=[21 * mm, 153 * mm], hAlign="LEFT")
    encabezado.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    factura = tipo == "factura"
    elementos = [
        encabezado, Spacer(1, 8 * mm),
        texto("Factura de demostración" if factura else "Informe de contratación", titulo),
        Spacer(1, 2 * mm),
        texto("Documento de demostración académica. Sin validez tributaria. No es un DTE."),
        texto(f"Referencia {solicitud.numero_documento}  |  {timezone.localtime(solicitud.creada_en):%d/%m/%Y %H:%M}"),
        texto(f"Identificador de solicitud {solicitud.referencia}"),
        texto("Receptor" if factura else "Datos de contacto", subtitulo),
    ]
    if factura:
        elementos.append(tabla([
            ["Razón social", solicitud.razon_social], ["RUT", solicitud.rut_facturacion],
            ["Giro", solicitud.giro], ["Dirección", solicitud.direccion_facturacion],
        ], [35 * mm, 139 * mm]))
    else:
        elementos.append(tabla([
            ["Nombre", f"{solicitud.nombre} {solicitud.apellido}"], ["RUT", solicitud.rut or "No registrado"],
            ["Correo", solicitud.correo], ["Teléfono", solicitud.telefono],
        ], [35 * mm, 139 * mm]))
    elementos.extend([
        texto("Servicio contratado", subtitulo),
        tabla([
            ["Servicio", solicitud.servicio],
            ["Fecha solicitada", solicitud.fecha.strftime("%d/%m/%Y")],
            ["Ubicación de la obra", f"{solicitud.direccion}, {solicitud.comuna}, {solicitud.region}"],
            ["Cantidad", solicitud.cantidad],
            ["Tarifa unitaria con IVA", pesos(solicitud.tarifa)],
        ], [50 * mm, 124 * mm]),
        Spacer(1, 5 * mm),
    ])
    totales = Table([
        [texto("Neto"), texto(pesos(solicitud.neto), importe)],
        [texto("IVA 19%"), texto(pesos(solicitud.iva), importe)],
        [texto("Total CLP", subtitulo), texto(pesos(solicitud.total), importe)],
    ], colWidths=[120 * mm, 54 * mm], hAlign="LEFT")
    totales.setStyle(TableStyle([
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#fbe3ee")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7),
    ]))
    elementos.extend([
        totales, texto("Seguimiento", subtitulo),
        texto(f"Medio de pago seleccionado  {solicitud.get_metodo_pago_display() or 'No registrado'}"),
        texto(f"Resultado del pago local  {'Aprobado' if solicitud.pago_aprobado else 'Rechazado'}"),
        texto(f"Estado de la solicitud  {solicitud.estado_visible}"),
    ])
    if solicitud.observaciones:
        elementos.extend([texto("Indicaciones", subtitulo), texto(solicitud.observaciones)])

    def pie(canvas, doc):
        canvas.setFont("BuildCorp", 8)
        canvas.setFillColor(colors.HexColor("#765568"))
        canvas.drawString(18 * mm, 12 * mm, "BuildCorp - Demostración académica - Sin validez tributaria")
        canvas.drawRightString(192 * mm, 12 * mm, f"Página {doc.page}")

    documento.build(elementos, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()
