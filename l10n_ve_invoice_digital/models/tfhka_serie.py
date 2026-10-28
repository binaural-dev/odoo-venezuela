from odoo import fields, models


class TfhkaSerie(models.Model):
    """Serie de documento registrada en TFHKA para esta compañía.

    Sincronizada desde /ConsultaNumeraciones cada vez que se genera el token
    (ver res.company._sync_tfhka_series) -- no es un catálogo que TFHKA emita
    por adelantado (a diferencia de UniDigital): la serie es un string que la
    propia compañía inventa la primera vez que llama a /AsignarNumeraciones,
    y esto solo permite leer de vuelta lo que ya se registró, para que los
    diarios puedan elegirlo en vez de escribirlo a mano."""

    # "NO APLICA" es lo que TFHKA devuelve para "sin serie" (un rango que
    # cubre cualquier tipo de documento, sin letras de serie reales). Se
    # sincroniza como un registro más -- un diario puede elegirlo
    # explícitamente para decir "este diario no usa serie" -- pero nunca se
    # le manda a TFHKA tal cual: ver account.journal._get_tfhka_series().
    NO_APLICA = "NO APLICA"

    _name = "tfhka.serie"
    _description = "TFHKA Document Series"
    _order = "name"

    name = fields.Char(string="Series", required=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    title = fields.Char(string="Title", help="TFHKA's own description of this numbering range (titulo).")
    document_type = fields.Char(string="Document Type", help="Document type this range applies to (tipoDocumento).")
    prefix = fields.Char(string="Prefix")
    number_from = fields.Char(string="Range Start", help="First document number in this range (desde).")
    number_to = fields.Char(string="Range End", help="Last document number in this range (hasta).")
    correlative = fields.Char(string="Current Correlative", help="Next document number TFHKA will assign in this range (correlativo).")
    status = fields.Char(string="Status in TFHKA")

    _sql_constraints = [
        (
            "name_company_uniq",
            "unique(name, company_id)",
            "This TFHKA series is already registered for this company.",
        ),
    ]

    def _sync_from_tfhka(self, company, numberings):
        """Crea/actualiza un registro por cada ``serie`` distinta presente en
        ``numberings`` (la respuesta cruda de ``tfhka.api.client.list_numberings``),
        incluida "NO APLICA" -- se sincroniza como cualquier otra para que un
        diario pueda elegirla explícitamente (ver NO_APLICA arriba).

        Una misma serie puede aparecer varias veces en la respuesta (una fila
        por tipo de documento con su propio rango) -- esto no modela esos
        rangos por tipo como registros separados, se queda con los datos de
        la última fila procesada para esa serie; el rango vigente de cada
        documento lo sigue validando ``query_numbering`` en el momento de
        emitir, contra TFHKA en vivo, no contra esta copia local. Solo se
        descarta una serie realmente vacía (sin nombre)."""
        for numbering in numberings:
            name = (numbering.get("serie") or "").strip()
            if not name:
                continue
            serie = self.search([
                ("name", "=", name),
                ("company_id", "=", company.id),
            ], limit=1)
            vals = {
                "name": name,
                "company_id": company.id,
                "title": numbering.get("titulo"),
                "document_type": numbering.get("tipoDocumento"),
                "prefix": numbering.get("prefijo"),
                "number_from": numbering.get("desde"),
                "number_to": numbering.get("hasta"),
                "correlative": numbering.get("correlativo"),
                "status": numbering.get("estado"),
            }
            if serie:
                serie.write(vals)
            else:
                self.create(vals)
