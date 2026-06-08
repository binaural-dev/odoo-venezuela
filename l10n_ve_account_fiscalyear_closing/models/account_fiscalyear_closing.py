import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, exceptions, fields, models , Command
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class AccountFiscalyearClosingConfig(models.Model):
    _inherit = "account.fiscalyear.closing.config"

    l_map = fields.Boolean(string="Load Accounts")

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
                            "income_other",
                            "expense_depreciation",
                            "expense_direct_cost",
                        ],
                    ),
                    ("company_ids", "in", [self.env.company.id, False]),
                ]
            )
        )

        config_a = (
            self.env["account.account"]
            .sudo()
            .search(
                [
                    ("account_type", "=", "equity_unaffected"),
                    ("company_ids", "in", [self.env.company.id, False]),
                ],
                limit=1,
            )
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
                    ("company_ids", "in", [self.fyc_id.company_id.id]),
                    ("code", "=ilike", account_map.src_accounts),
                ],
                order="code ASC",
            )
        else:
            src_accounts = (
                self.env["account.account"]
                .sudo()
                .search(
                    [
                        ("company_ids", "in", [self.fyc_id.company_id.id]),
                        ("code", "=ilike", src),
                    ]
                )
            )
        for account in src_accounts:
            closing_type = self.closing_type_get(account)
            balance = False
            if closing_type == "balance":
                # Get all lines
                lines = account_map.account_lines_get(account)

                balance, move_line, rate = account_map.move_line_prepare(account, lines)
                if move_line:
                    move_lines.append(move_line)
            elif closing_type == "unreconciled":
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


class AccountFiscalyearClosing(models.Model):
    _inherit = "account.fiscalyear.closing"

    @api.constrains('date_start', 'date_end')
    def _check_year_dates_consistency(self):
        for record in self:
            if record.year and record.date_start and record.date_end:
                start_year = record.date_start.year
                end_year = record.date_end.year
                
                if start_year != record.year or end_year != record.year:
                    raise ValidationError(_(
                        "Las fechas de inicio (%s) y fin (%s) deben pertenecer al año fiscal %s."
                    ) % (start_year, end_year, record.year))
                
                if record.date_start > record.date_end:
                    raise ValidationError(_("La fecha de inicio no puede ser posterior a la fecha de fin."))

    def draft_moves_check(self):
        for closing in self:
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

    def button_post(self):
        for closing in self:
            closing.move_ids.action_post()
        return super().button_post()

    # Todo el registro de las cuentas esta en esta funcion
    def calculate(self):
        dest_account = (
            self.env["account.account"]
            .sudo()
            .search(
                [
                    ("account_type", "=", "equity_unaffected"),
                    ("company_ids", "in", [self.company_id.id, False]),
                ],
                limit=1,
            )
        )
        currencies = {
            "bsd_id": self.env.company.currency_id,
            "foreign_currency": self.env.company.foreign_currency_id,
        }

        for closing in self:
            # Perform checks, raise exception if check fails
            if closing.check_draft_moves:
                closing.draft_moves_check()

            enabled_configs = closing.move_config_ids.filtered("enabled")
            if not enabled_configs:
                raise UserError(_("No existen configuraciones de asientos de cierre habilitadas. "
                                    "Por favor, verifique la pestaña 'Configuración de Movimientos'."))
    
            for config in enabled_configs:
                balances = self._get_balances(config)

                if not balances:
                    raise UserError(_("No se encontraron saldos para las cuentas de origen definidas en la configuración '%s'. "
                                        "Por favor, verifique que existan movimientos en el período seleccionado y que las cuentas de origen estén correctamente configuradas.") % config.name)
                self._create_closing_moves(config, balances, dest_account, currencies)

        return True
    

    def _get_balances(self, config):
        src_accounts = self.env["account.account"].search(
            [
                ("company_ids", "in", [self.company_id.id]),
                ("code", "in", config.mapping_ids.mapped("src_accounts")),
            ],
            order="code ASC",
        )

        domain = [
            ("company_id", "=", self.company_id.id),
            ("account_id", "in", src_accounts.ids),
            ("date", ">=", self.date_start),
            ("date", "<=", self.date_end),
            ("move_id.state", "!=", "cancel"),
        ]

        balances = self.env["account.move.line"].read_group(
            domain=domain,
            fields=["balance", "foreign_balance", "account_id"],
            groupby=["account_id"],
        )
        return balances

    def _create_closing_moves(self, config, balances, dest_account, currencies):
        """ Itera los balances y coordina la creación de los asientos. """
        for balance_dict in balances:
            balance = balance_dict.get("balance", 0.0)

            if balance == 0:
                continue

            move_vals = self._prepare_closing_move_vals(config, balance_dict, dest_account)
            
            move = self.env["account.move"].create(move_vals)

            move.write({"manually_set_rate": True})


    def _prepare_closing_move_vals(self, config, balance_dict, dest_account):
        balance = balance_dict.get("balance", 0.0)
        acc_id_raw = balance_dict.get("account_id")
        account_id = acc_id_raw[0] if isinstance(acc_id_raw, (list, tuple)) else acc_id_raw

        line_vals = [
            Command.create({
                "account_id": account_id,
                "currency_id": self.env.company.currency_id.id,
                "amount_currency": -balance,
                "name": config.name,
                "date": config.date,
            }),
            Command.create({
                "account_id": dest_account.id,
                "currency_id": self.env.company.currency_id.id,
                "amount_currency": balance,
                "name": _("Result"),
                "date": config.date,
            })
        ]

        return {
            "ref": config.name,
            "date": config.date,
            "fyc_id": self.id,
            "move_type": 'entry',
            "closing_type": config.move_type,
            "journal_id": config.journal_id.id,
            "manually_set_rate": False,
            "line_ids": line_vals,
        }

          

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
        bsd_id = self.env.ref("base.VEF").id
        if self.fyc_config_id.move_type == "opening":
            date = self.fyc_config_id.fyc_id.date_opening
        if account_lines:
            debits = sum(account_lines.mapped("debit"))
            credits = sum(account_lines.mapped("credit"))
            foreign_debits = sum(account_lines.mapped("foreign_debit"))
            foreign_credits = sum(account_lines.mapped("foreign_credit"))

            balance = debits - credits
            foreign_balance = foreign_debits - foreign_credits

            foreign_currency = account_lines[0].foreign_currency_id
            if not float_is_zero(balance, precision_digits=precision):
                rate = (
                    foreign_balance / balance
                    if balance > foreign_balance
                    else balance / foreign_balance
                )
               
                move_line = {
                    "account_id": account.id,
                    "debit": balance < 0 and -balance,
                    "credit": balance > 0 and balance,
                    "name": description,
                    "date": date,
                    "partner_id": partner_id,
                    "foreign_rate": rate,
                    "foreign_inverse_rate": (rate if bsd_id == foreign_currency.id else 1 / rate),
                }
            else:
                balance = 0
        return balance, move_line, abs(rate)

    def account_lines_get(self, account):
        self.ensure_one()
        start = self.fyc_config_id.fyc_id.date_start
        end = self.fyc_config_id.fyc_id.date_end
        company_id = self.fyc_config_id.fyc_id.company_id.id
        domain = [
            ("company_id", "=", company_id),
            # ("account_id", "=", account.id),
            ("date", ">=", start),
            ("date", "<=", end),
            ("move_id.state", "!=", "cancel"),
        ]
        return self.env["account.move.line"].read_group(
            domain=domain,
            fields=[
                "debit",
                "credit",
                "foreign_debit",
                "foreign_credit",
                "account_id",
            ],
            groupby=["account_id"],
        )

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
