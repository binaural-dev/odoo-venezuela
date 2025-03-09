from odoo import api, models

from ..tools.utils import get_is_foreign_currency


class ResCurrency(models.Model):
    _inherit = "res.currency"

    @api.model
    def _get_query_currency_table(self, options):
        """
        Inherits the original method to return the currency table of the foreign currency in cases
        in which the user is trying to get a report in the foreign currency.
        """
        is_foreign_currency = get_is_foreign_currency(self.env)
        if not is_foreign_currency:
            return super()._get_query_currency_table(options)
        user_company = self.env.company
        user_currency = user_company.currency_foreign_id
        if options.get("multi_company", False):
            companies = self.env.companies
            conversion_date = options["date"]["date_to"]
            currency_rates = companies.mapped("currency_foreign_id")._get_rates(
                user_company, conversion_date
            )
        else:
            companies = user_company
            currency_rates = {user_currency.id: 1.0}

        conversion_rates = []
        for company in companies:
            conversion_rates.extend(
                (
                    company.id,
                    currency_rates[user_company.currency_foreign_id.id]
                    / currency_rates[company.currency_foreign_id.id],
                    user_currency.decimal_places,
                )
            )
        query = "(VALUES %s) AS currency_table(company_id, rate, precision)" % ",".join(
            "(%s, %s, %s)" for i in companies
        )
        return self.env.cr.mogrify(query, conversion_rates).decode(self.env.cr.connection.encoding)
