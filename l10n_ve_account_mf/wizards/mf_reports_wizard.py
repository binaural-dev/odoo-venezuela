from odoo import _, fields, models
from odoo.exceptions import ValidationError


class MfReportsWizard(models.TransientModel):
    _name = "l10n_ve.mf.reports.wizard"
    _description = "Fiscal Machine Reports Wizard"

    # ------------------------------------------------------------------
    # Rango de fechas compartido por el reporte de memoria fiscal (I2)
    # y por la reimpresion de documentos "por fecha" (Rf/Rc/Rz/...).
    # NO aplica al Reporte X/Z diario (I0X/I0Z), que siempre corresponden
    # al dia fiscal en curso segun el protocolo TFHKA.
    # ------------------------------------------------------------------
    date_from = fields.Date(
        required=True,
        default=fields.Date.today,
        help="Aplica al reporte de memoria fiscal por rango y a la "
        "reimpresion de documentos por fecha. El Reporte X y el Reporte Z "
        "corresponden siempre al dia fiscal en curso; no usan este rango.",
    )
    date_to = fields.Date(
        required=True,
        default=fields.Date.today,
        help="Aplica al reporte de memoria fiscal por rango y a la "
        "reimpresion de documentos por fecha.",
    )

    # ------------------------------------------------------------------
    # Reporte de memoria fiscal por fecha (comando I2<tipo>, Tabla 61
    # del Manual de Protocolos y Comandos TFHKA V8.5.0).
    # ------------------------------------------------------------------
    memory_report_type = fields.Selection(
        selection=[
            ("S", "Resumen (I2S)"),
            ("A", "Detallado (I2A)"),
            ("M", "Mensual (I2M)"),
        ],
        string="Tipo de reporte de memoria",
        default="S",
        required=True,
        help="Resumen (I2S), Detallado (I2A) o Mensual (I2M) de la memoria "
        "fiscal para el rango de fechas seleccionado.",
    )

    # ------------------------------------------------------------------
    # Reimpresion de documentos de la memoria de auditoria, POR NUMERO
    # (comando en mayuscula + rango numerico de 7 digitos, Tabla 39 del
    # Manual TFHKA V8.5.0).
    #
    # La reimpresion "por fecha" (comandos en minuscula Rf/Rz/..., Tabla 40)
    # se retiro a proposito: en los equipos probados (HKA80) el firmware
    # acepta el comando pero NO devuelve el documento por fecha (imprime
    # vacio o responde NAK), aunque el mismo documento si se reimprime por
    # numero. Para consultas por rango de fechas esta el "Reporte de memoria
    # fiscal" (I2), que si funciona.
    # ------------------------------------------------------------------
    reprint_doc_type = fields.Selection(
        selection=[
            ("invoice", "Facturas"),
            ("refund", "Notas de Credito"),
            ("nofiscal", "Documentos no fiscales"),
            ("report_x", "Reporte X"),
            ("report_z", "Reporte Z"),
            ("all", "Todos los documentos"),
        ],
        string="Documento a reimprimir",
        default="report_z",
        required=True,
        help="Tipo de documento a reimprimir desde la memoria de auditoria, "
        "por rango de numero. 'Reporte Z' reimprime los cierres Z del rango.",
    )
    number_from = fields.Char(string="Numero desde")
    number_to = fields.Char(string="Numero hasta")

    def _validate_date_range(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise ValidationError(_("Date To must be greater than or equal to Date From."))

    def get_date_range_payload(self):
        self.ensure_one()
        self._validate_date_range()
        return {
            "date_from": self.date_from.strftime("%d%m%y"),
            "date_to": self.date_to.strftime("%d%m%y"),
        }
