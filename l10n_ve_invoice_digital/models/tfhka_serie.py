from odoo import fields, models


class TfhkaSerie(models.Model):
    """Serie de documento registrada en TFHKA para esta compañía.

    Sincronizada desde /ConsultaNumeraciones cada vez que se genera el token
    (ver res.company._sync_tfhka_series) -- no es un catálogo que TFHKA emita
    por adelantado (a diferencia de UniDigital): la serie es un string que la
    propia compañía inventa la primera vez que llama a /AsignarNumeraciones,
    y esto solo permite leer de vuelta lo que ya se registró, para que los
    diarios puedan elegirlo en vez de escribirlo a mano."""

    _name = "tfhka.serie"
    _description = "TFHKA Document Series"

    name = fields.Char(string="Series", required=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    prefix = fields.Char(string="Prefix")
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
        ``numberings`` (la respuesta cruda de ``tfhka.api.client.list_numberings``).

        Una misma serie puede aparecer varias veces en la respuesta (una fila
        por tipo de documento con su propio rango) -- esto no modela esos
        rangos por tipo, solo el nombre/prefijo/estado de la serie como tal,
        que es lo que necesita el diario para elegirla; el rango vigente de
        cada documento lo sigue validando ``query_numbering`` en el momento
        de emitir, contra TFHKA en vivo, no contra esta copia local.
        "NO APLICA" (lo que TFHKA devuelve para "sin serie") y una serie
        vacía se descartan: no son series elegibles por un diario."""
        for numbering in numberings:
            name = (numbering.get("serie") or "").strip()
            if not name or name == "NO APLICA":
                continue
            serie = self.search([
                ("name", "=", name),
                ("company_id", "=", company.id),
            ], limit=1)
            vals = {
                "name": name,
                "company_id": company.id,
                "prefix": numbering.get("prefijo"),
                "status": numbering.get("estado"),
            }
            if serie:
                serie.write(vals)
            else:
                self.create(vals)
