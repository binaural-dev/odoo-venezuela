from lxml import etree

from odoo import api, fields, models


class PosOrderReport(models.Model):
    _inherit = "report.pos.order"

    foreign_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Foreign Currency",
        readonly=True,
    )
    foreign_untaxed_total = fields.Monetary(
        string="Foreign Untaxed Total",
        readonly=True,
        currency_field="foreign_currency_id",
    )
    foreign_total_billed = fields.Monetary(
        string="Foreign Total Billed",
        readonly=True,
        currency_field="foreign_currency_id",
    )

    # Tasa (moneda alterna por unidad de la moneda de la compañía) a la que se
    # valora la línea: la de la venta original en un reembolso, igual que
    # ``pos.order._get_payment_foreign_rate`` y ``_refundOriginalRate`` del PdV,
    # para que la venta y su reembolso se anulen en la moneda alterna aunque se
    # hagan en días con tasas distintas. Si no, la tasa congelada del pedido.
    _FOREIGN_RATE_SQL = (
        "COALESCE(NULLIF(l10n_ve_refund_src_order.foreign_currency_rate, 0),"
        " s.foreign_currency_rate, 0.0)"
    )

    def _select(self):
        # Los montos en la moneda alterna se derivan de la línea y de la tasa,
        # igual que ``localToForeign`` del PdV. No se usan
        # ``foreign_subtotal``/``foreign_total`` de la línea porque en 19.0
        # nadie los escribe y quedarían en 0. El signo sigue la misma regla que
        # ``price_total`` del core para que los reembolsos resten.
        rate = self._FOREIGN_RATE_SQL
        return (
            super()._select()
            + f""",
                co.foreign_currency_id AS foreign_currency_id,
                ROUND(
                    ((SIGN(l.qty) * SIGN(l.price_unit) * ABS(l.price_subtotal))
                        * {rate})::numeric,
                    COALESCE(fcu.decimal_places, 2)
                ) AS foreign_untaxed_total,
                ROUND(
                    ((SIGN(l.qty) * SIGN(l.price_unit) * ABS(l.price_subtotal_incl))
                        * {rate})::numeric,
                    COALESCE(fcu.decimal_places, 2)
                ) AS foreign_total_billed
            """
        )

    def _from(self):
        # ``refunded_order_id`` no se guarda en la base en 19.0 (es calculado),
        # así que la venta original se alcanza por la línea reembolsada.
        return (
            super()._from()
            + """
                LEFT JOIN res_currency fcu ON (co.foreign_currency_id = fcu.id)
                LEFT JOIN pos_order_line l10n_ve_refund_src_line
                    ON (l10n_ve_refund_src_line.id = l.refunded_orderline_id)
                LEFT JOIN pos_order l10n_ve_refund_src_order
                    ON (l10n_ve_refund_src_order.id = l10n_ve_refund_src_line.order_id)
            """
        )

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        res = super().get_view(view_id, view_type, **options)
        # La vista se arma sin registros, así que no hay ``company_id`` del cual
        # tomar la moneda: la etiqueta usa la de la compañía activa.
        foreign_currency = self.env.company.foreign_currency_id
        if not foreign_currency or view_type not in ("pivot", "graph"):
            return res

        doc = etree.XML(res["arch"])
        labels = {
            "foreign_untaxed_total": self.env._("Subtotal %s", foreign_currency.name),
            "foreign_total_billed": self.env._("Total %s", foreign_currency.name),
        }
        for field_name, label in labels.items():
            for node in doc.xpath(f"//field[@name='{field_name}']"):
                node.set("string", label)
        res["arch"] = etree.tostring(doc, encoding="unicode")
        return res
