from odoo import api, fields, models, _
from odoo.tools import formatLang, float_is_zero
from datetime import timedelta
import pytz
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


import logging

_logger = logging.getLogger(__name__)


class ReportPaymentPos(models.AbstractModel):
    _name = "report.l10n_ve_pos.payment_report_pos"

    def get_datetime_tz(self, datetime):
        # get tz or by default
        timezone = self._context.get("tz") or self.env.user.partner_id.tz or "UTC"

        # convert date and time into user timezone
        self_tz = self.with_context(tz=timezone)

        result = fields.Datetime.context_timestamp(
            self_tz, fields.Datetime.from_string(datetime)
        )

        return result

    @api.model
    def _get_report_values(self, docids, data=None):

        # Fields date
        date_start = self.get_datetime_tz(data.get("date_start"))
        date_stop = self.get_datetime_tz(data.get("date_stop"))

        category_ids = data.get("category_ids")
        show_categories = data.get("show_categories")

        currency = self.env.company.currency_id
        foreign_currency = self.env.company.currency_foreign_id

        def get_payment_info(payments):
            return {
                "sale_count": len(payments.pos_order_id),
                "count": len(payments),
                "amount": sum(payments.mapped("amount")),
                "foreign_amount": sum(payments.mapped("foreign_amount")),
                "f_amount": formatLang(
                    self.env, sum(payments.mapped("amount")), currency_obj=currency
                ),
                "f_foreign_amount": formatLang(
                    self.env,
                    sum(payments.mapped("foreign_amount")),
                    currency_obj=foreign_currency,
                ),
            }

        def category_info(lines):
            return {
                "count": len(lines),
                "amount": sum(lines.mapped("price_total")),
                "foreign_amount": sum(lines.mapped("foreign_price_total")),
                "f_amount": formatLang(
                    self.env, sum(lines.mapped("price_total")), currency_obj=currency
                ),
                "f_foreign_amount": formatLang(
                    self.env,
                    sum(lines.mapped("foreign_price_total")),
                    currency_obj=foreign_currency,
                ),
            }

        def get_info(pos_config_id):
            config_id = self.env["pos.config"].browse(pos_config_id.ids)
            order_ids = self.env["pos.order"].search(
                [
                    ("config_id", "=", pos_config_id.ids),
                    ("date_order", ">=", date_start),
                    ("date_order", "<=", date_stop),
                ]
            )
            order_fiscal = self.env["pos.order"]
            order_no_fiscal = self.env["pos.order"]

            categories = []
            group_categories = {}

            payments = {"fiscal": {}, "no_fiscal": {}, "global": {}}
            payment_methods = []

            pos_categ = self.env["product.category"].search(
                [("id", "in", category_ids)]
            )

            for category in pos_categ:
                if show_categories in ["1_level", "both"]:
                    categories.append({"id": str(category.id), "name": category.name})
                if show_categories in ["2_level", "both"]:
                    for child in category.child_id:
                        if str(child.id) not in [c["id"] for c in categories]:
                            categories.append(
                                {"id": str(child.id), "name": " - " + child.name}
                            )

            for payment_method in config_id.payment_method_ids:
                payment_methods.append(
                    {
                        "id": str(payment_method.id),
                        "name": payment_method.name,
                    }
                )

            for order in order_ids:
                for line in order.account_move.invoice_line_ids:
                    category = str(line.product_id.categ_id.id)
                    if category in [c["id"] for c in categories]:
                        if group_categories.get(category, False):
                            group_categories[category] |= line
                        else:
                            group_categories[category] = line

                    if str(line.product_id.categ_id.parent_id.id) in [
                        c["id"] for c in categories
                    ]:
                        parent_category = str(line.product_id.categ_id.parent_id.id)
                        if group_categories.get(parent_category, False):
                            group_categories[parent_category] |= line
                        else:
                            group_categories[parent_category] = line

                for payment in order.payment_ids:
                    payment_method_id = str(payment.payment_method_id.id)
                    if payments["global"].get(payment_method_id, False):
                        payments["global"][payment_method_id] |= payment
                    else:
                        payments["global"][payment_method_id] = payment

                    if order.account_move.journal_id.fiscal:
                        order_fiscal |= order
                        if payments["fiscal"].get(payment_method_id, False):
                            payments["fiscal"][payment_method_id] |= payment
                        else:
                            payments["fiscal"][payment_method_id] = payment
                    else:
                        order_no_fiscal |= order
                        if payments["no_fiscal"].get(payment_method_id, False):
                            payments["no_fiscal"][payment_method_id] |= payment
                        else:
                            payments["no_fiscal"][payment_method_id] = payment

            def get_percentage(amount):
                if not order_ids.payment_ids:
                    return 0
                percentage = round(
                    amount * 100 / get_payment_info(order_ids.payment_ids)["amount"], 2
                )
                return f"{percentage:.2f} %"

            return {
                "all_payments": order_ids.payment_ids,
                "payments": payments,
                "payment_methods": payment_methods,
                "categories": categories,
                "group_categories": group_categories,
                "get_percentage": get_percentage,
            }

        range_date = f"{date_start.strftime(DEFAULT_SERVER_DATETIME_FORMAT)} - {date_stop.strftime(DEFAULT_SERVER_DATETIME_FORMAT)}"

        return {
            "docs": self.env["pos.config"],
            "get_info": get_info,
            "get_payment_info": get_payment_info,
            "get_category_info": category_info,
            "range_date": range_date,
            "data": data,
            "currency": currency,
            "foreign_currency": foreign_currency,
        }
