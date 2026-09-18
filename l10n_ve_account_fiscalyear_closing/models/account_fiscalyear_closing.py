import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, exceptions, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class AccountFiscalyearClosingMappingIdSrc(models.Model):
    _inherit = ["account.fiscalyear.closing.mapping", "mail.thread", "mail.activity.mixin"]

    # src_accounts (Char) matchea por codigo, ambiguo si hay cuentas
    # duplicadas con el mismo codigo (comun tras migraciones de plan de
    # cuentas). src_account_id fija sin ambiguedad la cuenta real; se
    # completa automaticamente en onchange_l_map.
    src_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Source account",
    )


class AccountFiscalyearClosingConfig(models.Model):
    _inherit = "account.fiscalyear.closing.config"

    l_map = fields.Boolean(string="Load Accounts")
    
    @api.onchange("l_map")
    def onchange_l_map(self):
        # La compania del cierre (fyc_id.company_id), NO la compania activa
        # de la sesion (self.env.company): con varias companias, la activa
        # puede no ser la del cierre que se esta configurando, y companias
        # distintas suelen repetir el mismo codigo de cuenta.
        company = self.fyc_id.company_id or self.env.company
        accounts = (
            self.env["account.account"]
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
                    ("company_ids", "in", [company.id, False]),
                ]
            )
        )

        config_a = (
            self.env["account.account"]
            .search(
                [
                    ("account_type", "=", "equity_unaffected"),
                    ("company_ids", "in", [company.id, False]),
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
                        "src_account_id": a.id,
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
        rate = 1.0

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
    _inherit = ["account.fiscalyear.closing", "mail.thread", "mail.activity.mixin"]

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
            # move_ids keeps cancelled entries from earlier recalculations
            # around for audit (see account_fiscal_year_closing.py's
            # _moves_remove); action_post() on an already-cancelled move
            # raises, so only post the ones still active.
            closing.active_move_ids.action_post()
        return super().button_post()

    # Todo el registro de las cuentas esta en esta funcion
    def calculate(self):
        # _check_fiscal_lock_date se hereda tal cual del modulo base
        # (account_fiscal_year_closing); solo se invoca aqui porque este
        # metodo redefine calculate() por completo, sin llamar a super().
        self._check_fiscal_lock_date()

        for closing in self:
            # dest_account y currencies deben calcularse por cada closing
            # usando closing.company_id: sobre un recordset multi-registro
            # (y potencialmente multi-compania) self.company_id no tiene
            # sentido, y self.env.company es la compania activa de sesion
            # del usuario, no necesariamente la del cierre que se procesa.
            dest_account = (
                self.env["account.account"]
                .search(
                    [
                        ("account_type", "=", "equity_unaffected"),
                        ("company_ids", "in", [closing.company_id.id, False]),
                    ],
                    limit=1,
                )
            )
            if not dest_account:
                raise UserError(
                    _(
                        "No account of type 'Current Year Earnings' "
                        "(equity_unaffected) found configured for company "
                        "%(company)s. Configure the chart of accounts "
                        "before performing the fiscal closing."
                    )
                    % {"company": closing.company_id.display_name}
                )
            currencies = {
                "bsd_id": self.env.ref("base.VEF"),
                "foreign_currency": closing.company_id.foreign_currency_id,
            }

            # Perform checks, raise exception if check fails
            if closing.check_draft_moves:
                closing.draft_moves_check()

            skipped_accounts = self.env["account.account"]
            for config in closing.move_config_ids.filtered("enabled"):
                balances, mapped_accounts = closing._get_balances(config)
                accounts_with_balance = self.env["account.account"].browse(
                    b["account_id"][0] for b in balances
                )
                skipped_accounts |= closing._create_closing_moves(
                    config, balances, dest_account, currencies
                )
                # Cuentas mapeadas que ni siquiera aparecen en "balances":
                # no tuvieron ninguna linea posteada en el periodo (distinto
                # de tener saldo 0 por movimientos que se cancelan entre si).
                skipped_accounts |= mapped_accounts - accounts_with_balance

            if skipped_accounts:
                closing.message_post(
                    body=_(
                        "Las siguientes cuentas mapeadas no generaron linea "
                        "de cierre por no tener saldo (en bolivares ni en "
                        "moneda alterna) en el periodo %(start)s - %(end)s: "
                        "%(accounts)s."
                    )
                    % {
                        "start": closing.date_start,
                        "end": closing.date_end,
                        "accounts": ", ".join(
                            "%s %s" % (a.code, a.name) for a in skipped_accounts
                        ),
                    }
                )

            # Sin esto, un cierre sin ninguna cuenta con saldo en el periodo
            # (o sin ninguna configuracion habilitada) pasaba a "calculated"
            # en silencio, con 0 asientos generados, indistinguible en la UI
            # de un cierre que si genero asientos. Se usa active_move_ids
            # (no move_ids) porque move_ids conserva para siempre los
            # asientos cancelados de recalculos anteriores de un cierre ya
            # posteado, asi que nunca queda vacio y esta validacion nunca
            # dispararia en ese escenario si se usara move_ids.
            if not closing.active_move_ids:
                raise UserError(
                    _(
                        "No fiscal closing entries were generated for "
                        "%(company)s between %(start)s and %(end)s: none of "
                        "the mapped accounts had a balance to close in that "
                        "period. Check the account mappings and the period "
                        "dates before calculating again."
                    )
                    % {
                        "company": closing.company_id.display_name,
                        "start": closing.date_start,
                        "end": closing.date_end,
                    }
                )

        return True

    def _get_balances(self, config):
        # src_account_id (id) es la fuente de verdad: src_accounts (codigo)
        # es ambiguo si hay cuentas duplicadas con el mismo codigo. Solo se
        # cae a codigo para mappings viejos sin src_account_id todavia.
        mapped_ids = config.mapping_ids.filtered("src_account_id").mapped(
            "src_account_id"
        )
        codes_without_id = config.mapping_ids.filtered(
            lambda m: not m.src_account_id
        ).mapped("src_accounts")
        src_accounts = mapped_ids
        if codes_without_id:
            src_accounts |= self.env["account.account"].search(
                [
                    ("company_ids", "in", [self.company_id.id]),
                    ("code", "in", codes_without_id),
                ],
                order="code ASC",
            )

        domain = [
            ("company_id", "=", self.company_id.id),
            ("account_id", "in", src_accounts.ids),
            ("date", ">=", self.date_start),
            ("date", "<=", self.date_end),
            ("move_id.state", "=", "posted"),
        ]

        balances = self.env["account.move.line"].read_group(
            domain=domain,
            fields=["balance", "foreign_balance", "account_id"],
            groupby=["account_id"],
        )
        return balances, src_accounts

    def _create_closing_moves(self, config, balances, dest_account, currencies):
        vals = []
        skipped_accounts = self.env["account.account"]
        company_currency = self.company_id.currency_id
        foreign_currency = currencies.get("foreign_currency")

        for balance_dict in balances:
            balance = company_currency.round(balance_dict.get("balance", 0) or 0)
            foreign_balance = balance_dict.get("foreign_balance", 0) or 0
            if foreign_currency:
                foreign_balance = foreign_currency.round(foreign_balance)
            # Saltar solo si no hay nada que cerrar en NINGUNA moneda. En
            # bimoneda, una cuenta puede tener saldo real en bolivares sin
            # tener ningun movimiento en dolares (foreign_balance == 0) y
            # aun asi debe cerrarse; exigir foreign_balance != 0 la
            # descartaba por completo.
            if balance == 0 and foreign_balance == 0:
                skipped_accounts |= self.env["account.account"].browse(
                    balance_dict["account_id"][0]
                )
                continue

            vals.append(
                {
                    "ref": config.name,
                    "date": config.date,
                    "fyc_id": self.id,
                    "closing_type": config.move_type,
                    "journal_id": config.journal_id.id,
                    # manually_set_rate/foreign_rate/foreign_inverse_rate no se
                    # setean: el foreign_balance de cada linea ya viene
                    # extraido de los datos reales de account_move_line, no se
                    # deriva ninguna tasa sintetica a partir de los totales.
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "account_id": balance_dict["account_id"][0],
                                # amount_currency siempre en moneda de la
                                # compania: es el campo maestro, de ahi
                                # Odoo deriva debit/credit correctamente.
                                # No fijar "currency_id"/"amount_currency"
                                # explicitos dejaba que el asiento heredara
                                # la moneda del diario y Odoo recalculara
                                # amount_currency solo, a la tasa del dia
                                # del cierre (no la del periodo cerrado).
                                "currency_id": company_currency.id,
                                "amount_currency": -balance,
                                # foreign_balance (alterno) debe respetar el
                                # signo de amount_currency, no el suyo
                                # propio: aqui ambos se invierten igual.
                                "foreign_balance": -foreign_balance,
                                "not_foreign_recalculate": True,
                                "name": config.name,
                                "date": config.date,
                            },
                        ),
                        (
                            0,
                            0,
                            {
                                "account_id": dest_account.id,
                                "currency_id": company_currency.id,
                                "amount_currency": balance,
                                "foreign_balance": foreign_balance,
                                "not_foreign_recalculate": True,
                                "name": _("Result"),
                                "date": config.date,
                            },
                        ),
                    ],
                }
            )
        self.env["account.move"].create(vals)
        return skipped_accounts


class AccountFiscalyearClosingMapping(models.Model):
    _inherit = "account.fiscalyear.closing.mapping"

    def move_line_prepare(self, account, account_lines, partner_id=False):
        self.ensure_one()
        move_line = {}
        balance = 0
        precision = self.env["decimal.precision"].precision_get("Account")
        description = self.name or account.name
        date = self.fyc_config_id.fyc_id.date_end
        rate = 1.0
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
            # balance = sum(account_lines.mapped("debit")) - sum(account_lines.mapped("credit"))

            # foreign_balance = sum(account_lines.mapped("foreign_debit")) - sum(
            #     account_lines.mapped("foreign_credit")
            # )
            foreign_currency = account_lines[0].foreign_currency_id
            if not float_is_zero(balance, precision_digits=precision):
                rate = (
                    foreign_balance / balance
                    if balance > foreign_balance
                    else balance / foreign_balance
                )
                # for line in account_lines:
                # _logger.warning("NO ENTIENDO")
                #
                # line.move_id.write(
                #     {
                #         "manually_set_rate": True,
                #         "foreign_inverse_rate": rate
                #         if bsd_id == foreign_currency.id
                #         else 1 / rate,
                #         "foreign_rate": rate,
                #     }
                # )
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
