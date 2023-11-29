import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, exceptions, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class AccountFiscalyearClosingConfig(models.Model):
    _inherit = "account.fiscalyear.closing.config"

    @api.onchange("l_map")
    def onchange_l_map(self):
        accounts = (
            self.env["account.account"]
            .sudo()
            .search(
                [
                    (
                        "account_type",
                        "in",
                        [
                            "income",
                            "expense",
                            "other_income",
                            "expense_depreciation",
                            "expense_direct_cost",
                        ],
                    )
                ]
            )
        )

        config_a = (
            self.env["account.account"]
            .sudo()
            .search([("account_type", "=", "equity_unaffected")], limit=1)
        )  # esta es la de destino siempre es la misma preguntar cual es
        maps = []
        cont = 1
        if self.l_map:
            # sync
            for a in accounts:
                if len(a.code):
                    vals = {
                        "name": a.name,
                        "src_accounts": a.code,
                        "dest_account_id": config_a.id,
                        "fyc_config_id": self.id,
                    }
                    cont += 1
                    maps.append((0, 0, vals))
            if len(maps) > 0:
                # self.update({'mapping_ids':maps})
                return {"value": {"mapping_ids": maps}}
        else:
            return {"value": {"mapping_ids": [(5, 0, 0)]}}

    l_map = fields.Boolean(string="Load Accounts")

    def move_prepare(self, move_lines, rate=0):
        self.ensure_one()
        description = self.name
        journal_id = self.journal_id.id
        return {
            "ref": description,
            "date": self.date,
            "fyc_id": self.fyc_id.id,
            "closing_type": self.move_type,
            "journal_id": journal_id,
            "line_ids": [(0, 0, m) for m in move_lines],
            "foreign_rate": rate,  # Aqui va la informacion la tasa de las lineas
        }

    def _mapping_move_lines_get(self, src, account_map):
        move_lines = []
        dest_totals = {}
        # Add balance/unreconciled move lines
        # for account_map in self.mapping_ids:
        rate = 1

        dest = account_map.dest_account_id
        dest_totals.setdefault(dest, 0)
        # aqui filtrar si viene src usar solo esa
        if not src:
            src_accounts = self.env["account.account"].search(
                [
                    ("company_id", "=", self.fyc_id.company_id.id),
                    ("code", "=ilike", account_map.src_accounts),
                ],
                order="code ASC",
            )
        else:
            src_accounts = self.env["account.account"].sudo().search([("code", "=ilike", src)])
        # _logger.info("CANTIDAD DE src_accounts %s",len(src_accounts))
        for account in src_accounts:
            closing_type = self.closing_type_get(account)
            balance = False
            if closing_type == "balance":
                # Get all lines
                lines = account_map.account_lines_get(account, self.fyc_id.journal_type)

                balance, move_line, rate = account_map.move_line_prepare(account, lines)
                if move_line:
                    move_lines.append(move_line)
            elif closing_type == "unreconciled":
                # Get credit and debit grouping by partner
                # """partners = account_map.account_partners_get(account)
                # for partner in partners:
                #     balance, move_line = account_map.
                #         move_line_partner_prepare(account, partner)
                #     if move_line:
                #         move_lines.append(move_line)"""
                continue
            else:
                # Account type has unsupported closing method
                continue
            if dest and balance:
                dest_totals[dest] -= balance
        # Add destination move lines, if any
        for account_map in self.mapping_ids.filtered("dest_account_id"):
            dest = account_map.dest_account_id
            balance = dest_totals.get(dest, 0)
            if not balance:
                continue
            dest_totals[dest] = 0
            move_line = account_map.dest_move_line_prepare(dest, balance)
            if move_line:
                move_lines.append(move_line)
        return move_lines, rate

    def moves_create(self):
        self.ensure_one()
        moves = self.env["account.move"]
        # Prepare one move per configuration
        data = False

        rate = 1
        _logger.info(
            "funcion moves_create self.mapping_ids.filtered('dest_account_id') %s", self.mapping_ids
        )
        for ac in self.mapping_ids:
            # _logger.info("src_accountssrc_accounts------------------------------------------------------ %s",ac.src_accounts)
            # for c in ac.src_accounts:
            data = False
            if self.mapping_ids:
                move_lines, rate = self._mapping_move_lines_get(ac.src_accounts, ac)
                if len(move_lines) > 0:
                    data = self.move_prepare(move_lines, rate)
            elif self.inverse:
                # alerta: el move_id es un many2one
                move_ids = self.inverse_move_prepare()
                move = moves.browse(move_ids[0])
                move.write({"ref": self.name, "closing_type": self.move_type})
                self.move_id = move.id
                return move, data
            # Create move
            if not data:
                continue
                # return False, data
            total_debit = sum([x[2]["debit"] for x in data["line_ids"]])
            total_credit = sum([x[2]["credit"] for x in data["line_ids"]])

            dif = total_credit - total_debit

            if dif != 0:  # OJITO CON ESTO que genera otro asiento para sacar la diferencia
                other_dest = False
                for line in data["line_ids"]:
                    if len(line) >= 2:
                        if line[2]["name"] in ["Resultado", "Result"]:
                            other_dest = {
                                "account_id": line[2]["account_id"],
                                "name": "Ajuste por precisión decimal",
                                "date": line[2]["date"],
                                "debit": abs(dif) if dif > 0 else False,
                                "credit": abs(dif) if dif < 0 else False,
                            }
                if other_dest:
                    data["line_ids"].append((0, 0, other_dest))
            # el modulo valida pero con 2 decimales mientras que odoo manda las lineas con muchos decimales
            total_debit = sum([x[2]["debit"] for x in data["line_ids"]])
            total_credit = sum([x[2]["credit"] for x in data["line_ids"]])

            if abs(round(total_credit - total_debit, 2)) >= 0.01:  # Esto redondea
                # the move is not balanced
                return False, data
            move = moves.with_context(journal_id=self.journal_id.id).create(data)
            # self.move_id = move.id
            # este move_id debe ser para el inversal, duda
            if move:
                # move._onchange_rate() OJO CON ESTO, NO SE QUE HACE XD
                move._onchange_foreign_rate()
        return move, data


class AccountFiscalyearClosing(models.Model):
    _inherit = "account.fiscalyear.closing"

    journal_type = fields.Selection(
        [
            ("fiscal", "Fiscal Dairy"),
            ("nofiscal", "No Fiscal Dairy"),
            ("all", "All Dairy"),
        ],
        default="all",
    )

    def draft_moves_check(self):
        for closing in self:
            _logger.info("CHECK DRAFT %s", closing.journal_type)
            if closing.journal_type == "fiscal":
                draft_moves = self.env["account.move"].search(
                    [
                        ("company_id", "=", closing.company_id.id),
                        ("state", "=", "draft"),
                        ("date", ">=", closing.date_start),
                        ("date", "<=", closing.date_end),
                        ("journal_id.fiscal", "=", True),
                    ]
                )
            elif closing.journal_type == "nofiscal":
                draft_moves = self.env["account.move"].search(
                    [
                        ("company_id", "=", closing.company_id.id),
                        ("state", "=", "draft"),
                        ("date", ">=", closing.date_start),
                        ("date", "<=", closing.date_end),
                        ("journal_id.fiscal", "=", False),
                    ]
                )
            else:
                draft_moves = self.env["account.move"].search(
                    [
                        ("company_id", "=", closing.company_id.id),
                        ("state", "=", "draft"),
                        ("date", ">=", closing.date_start),
                        ("date", "<=", closing.date_end),
                    ]
                )
            if draft_moves:
                msg = _("Se encontraron uno o más movimientos sin asentar: \n")
                for move in draft_moves:
                    msg += "ID: %s, Date: %s, Number: %s, Ref: %s\n" % (
                        move.id,
                        move.date,
                        move.name,
                        move.ref,
                    )
                raise ValidationError(msg)
        return True


class AccountFiscalyearClosingMapping(models.Model):
    _inherit = "account.fiscalyear.closing.mapping"

    def move_line_prepare(self, account, account_lines, partner_id=False):
        self.ensure_one()
        move_line = {}
        balance = 0
        precision = self.env["decimal.precision"].precision_get("Account")
        description = self.name or account.name
        date = self.fyc_config_id.fyc_id.date_end
        rate = 1
        if self.fyc_config_id.move_type == "opening":
            date = self.fyc_config_id.fyc_id.date_opening
        if account_lines:
            balance = sum(account_lines.mapped("debit")) - sum(account_lines.mapped("credit"))
            foreign_balance = sum(account_lines.mapped("foreign_debit")) - sum(
                account_lines.mapped("foreign_credit")
            )

            if not float_is_zero(balance, precision_digits=precision):
                rate = sum(account_lines.mapped("foreign_rate")) / len(account_lines)
                move_line = {
                    "account_id": account.id,
                    "debit": balance < 0 and -balance,
                    "credit": balance > 0 and balance,
                    "foreign_debit": foreign_balance < 0 and -foreign_balance,
                    "foreign_credit": foreign_balance > 0 and foreign_balance,
                    "name": description,
                    "date": date,
                    "partner_id": partner_id,
                }
            else:
                balance = 0
        return balance, move_line, abs(rate)

    def account_lines_get(self, account, journal_type):
        self.ensure_one()
        start = self.fyc_config_id.fyc_id.date_start
        end = self.fyc_config_id.fyc_id.date_end
        company_id = self.fyc_config_id.fyc_id.company_id.id
        domain = [
            ("company_id", "=", company_id),
            ("account_id", "=", account.id),
            ("date", ">=", start),
            ("date", "<=", end),
        ]
        if journal_type == "fiscal":
            domain = domain + [("move_id.journal_id.fiscal", "=", True)]
            return self.env["account.move.line"].search(domain)
        elif journal_type == "nofiscal":
            domain = domain + [("move_id.journal_id.fiscal", "=", False)]
            return self.env["account.move.line"].search(domain)
        else:
            return self.env["account.move.line"].search(domain)

    def account_partners_get(self, account):
        self.ensure_one()
        start = self.fyc_config_id.fyc_id.date_start
        end = self.fyc_config_id.fyc_id.date_end
        company_id = self.fyc_config_id.fyc_id.company_id.id
        return self.env["account.move.line"].read_group(
            [
                ("company_id", "=", company_id),
                ("account_id", "=", account.id),
                ("date", ">=", start),
                ("date", "<=", end),
            ],
            ["partner_id", "credit", "debit"],
            ["partner_id"],
        )
