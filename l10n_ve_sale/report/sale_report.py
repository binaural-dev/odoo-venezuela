from lxml import etree
from odoo import fields, models, _, api


class SaleReport(models.Model):
    _inherit = 'sale.report'

    foreign_currency_id = fields.Many2one(comodel_name='res.currency', readonly=True)
    foreign_untaxed_total = fields.Monetary(string="Foreign Untaxed Total", readonly=True, currency_field='foreign_currency_id')
    foreign_total_billed = fields.Monetary(string="Foreign Total Billed", readonly=True, currency_field='foreign_currency_id')

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        res.update({
            'foreign_untaxed_total': """SUM(l.foreign_subtotal)""",
            'foreign_total_billed': """SUM(l.foreign_subtotal + (l.foreign_subtotal / COALESCE(NULLIF(l.price_subtotal, 0.0), 1.0) * (l.price_total - l.price_subtotal)))""",
            'foreign_currency_id': """s.foreign_currency_id""",
        })
        return res

    def _group_by_sale(self):
        res = super()._group_by_sale()
        res += """,
            s.foreign_currency_id"""
        return res

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        foreign_currency_id = self.env.company.foreign_currency_id
        res = super().get_view(view_id, view_type, **options)

        if foreign_currency_id and view_type == "pivot":
            foreign_currency_name = foreign_currency_id.name
            doc = etree.XML(res["arch"])
            foreign_total_billed = doc.xpath("//field[@name='foreign_total_billed']")
            if foreign_total_billed:
                foreign_total_billed[0].set("string", _("Total") + " " + foreign_currency_name)
            
            foreign_untaxed_total = doc.xpath("//field[@name='foreign_untaxed_total']")
            if foreign_untaxed_total:
                foreign_untaxed_total[0].set("string", _("Subtotal") + " " + foreign_currency_name)

            res["arch"] = etree.tostring(doc, encoding="unicode")
                
        return res
