from odoo import api, fields, models, _


class AccountFiscalyearClosing(models.Model):
    _inherit = "account.fiscalyear.closing"

    def _get_balances(self, config):
        src_accounts = self.env["account.account"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("code", "in", config.mapping_ids.mapped("src_accounts")),
            ],
            order="code ASC",
        )

        query = """
            SELECT
                distribution.analytic_account_id AS analytic_account_id,
                aml.account_id,
                SUM(
                    COALESCE(balance * (distribution.percentage::float / 100.0), balance)
                ) AS balance,
                SUM(
                    COALESCE(
                        foreign_balance * (distribution.percentage::float / 100.0),
                        foreign_balance
                    )
                ) AS foreign_balance
            FROM
                account_move_line aml
            LEFT JOIN
                LATERAL JSONB_EACH_TEXT(
                    aml.analytic_distribution
                ) AS distribution(analytic_account_id, percentage)
                    ON true
            LEFT JOIN
                (
                    SELECT
                        id, is_subsidiary
                    FROM
                        account_analytic_account
                    WHERE is_subsidiary = true
                ) AS analytic_acc
                ON analytic_acc.id = distribution.analytic_account_id::integer
            LEFT JOIN
                account_move AS am
                    ON aml.move_id = am.id
            WHERE
                aml.company_id = %s AND
                aml.account_id IN %s AND
                aml.date BETWEEN %s AND %s AND
                am.state != 'cancel'
            GROUP BY
                distribution.analytic_account_id, aml.account_id
            ;
        """

        params = (self.company_id.id, tuple(src_accounts.ids), self.date_start, self.date_end)
        self._cr.execute(query, params)
        balances = self.env.cr.dictfetchall()
        return balances

    def _create_closing_moves(self, config, balances, dest_account, currencies):
        vals = []
        for balance_dict in balances:
            balance = balance_dict.get("balance", 0)
            analytic_account = balance_dict.get("analytic_account_id", False)
            foreign_balance = balance_dict.get("foreign_balance", 0)
            if (currencies["bsd_id"] == currencies["foreign_currency"] and balance == 0) or (
                currencies["bsd_id"] != currencies["foreign_currency"] and foreign_balance == 0
            ):
                continue
            rate = abs(
                foreign_balance / balance
                if currencies["bsd_id"] == currencies["foreign_currency"]
                else balance / foreign_balance
            )
            move_vals = {
                "ref": config.name,
                "date": config.date,
                "fyc_id": self.id,
                "closing_type": config.move_type,
                "journal_id": config.journal_id.id,
                "manually_set_rate": True,
                "foreign_rate": rate,
                "foreign_inverse_rate": (
                    rate if currencies["bsd_id"] == currencies["foreign_currency"] else 1 / rate
                ),
                "account_analytic_id": (
                    int(analytic_account) if analytic_account is not None else False
                ),
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": balance_dict["account_id"],
                            "balance": -balance,
                            "name": config.name,
                            "date": config.date,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": dest_account.id,
                            "balance": balance,
                            "name": _("Result"),
                            "date": config.date,
                        },
                    ),
                ],
            }
            vals.append(move_vals)
        self.env["account.move"].sudo().create(vals)
