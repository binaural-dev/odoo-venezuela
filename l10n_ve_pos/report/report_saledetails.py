from odoo import api, models


class ReportSaleDetails(models.AbstractModel):
    _inherit = "report.point_of_sale.report_saledetails"

    @api.model
    def get_sale_details(
        self, date_start=False, date_stop=False, config_ids=False, session_ids=False, **kwargs
    ):
        """Extend the native report with the company's foreign currency totals.

        Delegates the whole native structure (categories, refunds, taxes,
        discounts, invoices, cash count) to core `point_of_sale`, and only adds
        the Bs/USD dual amounts on top of the payments section.
        """
        res = super().get_sale_details(
            date_start, date_stop, config_ids, session_ids, **kwargs
        )

        foreign_currency = self.env.company.foreign_currency_id
        res["foreign_currency"] = foreign_currency
        res["foreign_total_paid"] = 0.0
        if not foreign_currency:
            return res

        orders = self.env["pos.order"].search(
            self._get_domain(date_start, date_stop, config_ids, session_ids)
        )
        payment_ids = self.env["pos.payment"].search(
            [("pos_order_id", "in", orders.ids)]
        ).ids

        foreign_by_key = {}
        if payment_ids:
            self.env.cr.execute(
                """
                SELECT method.id AS id, payment.session_id AS session,
                       sum(payment.foreign_amount) AS f_total
                FROM pos_payment AS payment
                JOIN pos_payment_method AS method ON payment.payment_method_id = method.id
                WHERE payment.id IN %s
                GROUP BY method.id, payment.session_id
                """,
                (tuple(payment_ids),),
            )
            for row in self.env.cr.dictfetchall():
                foreign_by_key[(row["id"], row["session"])] = row["f_total"]

        for payment in res["payments"]:
            payment["f_total"] = foreign_by_key.get(
                (payment.get("id"), payment.get("session")), 0.0
            )

        payments_per_method = {}
        for payment in res["payments"]:
            if payment.get("id"):
                entry = payments_per_method.setdefault(
                    payment["id"],
                    {
                        "id": payment["id"],
                        "name": self.env["pos.payment.method"].browse(payment["id"]).name,
                        "total": 0.0,
                        "f_total": 0.0,
                    },
                )
                entry["total"] += payment["total"]
                entry["f_total"] += payment["f_total"]
        res["payments_per_method"] = payments_per_method.values()

        res["foreign_total_paid"] = foreign_currency.round(sum(foreign_by_key.values()))
        return res
