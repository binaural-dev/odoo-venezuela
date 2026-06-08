import logging
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, api, exceptions, fields, models , Command
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class AccountFiscalyearClosingConfig(models.Model):
    _inherit = "account.fiscalyear.closing.config"

    l_map = fields.Boolean(string="Load Accounts")

    journal_id = fields.Many2one(
        'account.journal',
        domain=lambda self: [('type', '=', 'general')],
    )

    inverse_config_id = fields.Many2one(
        "account.fiscalyear.closing.config",
        string="Reverse entry from",
        domain=lambda self: [
            ('fyc_id', '=', self.fyc_id.id),
            ('id', '!=', self.id),
            ('move_type', '=', 'closing'),
            ('state', '=', 'posted'),
        ] if self.fyc_id else [],
    )

    @api.onchange('inverse_config_id')
    def _onchange_inverse_config_id(self):
        if self.inverse_config_id:
            self.move_type = 'opening'
        else:
            self.move_type = 'closing'

    @api.onchange('move_type')
    def _check_inverse_config_move_type(self):
        for config in self:
            if config.inverse_config_id and config.move_type == 'closing':
                raise UserError(_(
                    "A configuration with 'Reverse entry from' must not be of type 'closing'."
                ))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'move_type' in fields_list and not res.get('move_type'):
            res['move_type'] = 'closing'
        if res.get('move_type') == 'closing' and 'date' in fields_list and not res.get('date'):
            fyc_id = self.env.context.get('default_fyc_id') or self.env.context.get('active_id')
            if fyc_id:
                fyc = self.env['account.fiscalyear.closing'].browse(fyc_id)
                if fyc.exists():
                    res['date'] = fyc.date_end
        return res

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
            "closing_type": "closing",
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

    closing_grouping = fields.Selection([
        ("single", "1 entry per type (consolidates accounts)"),
        ("config", "1 entry per configuration"),
        ("account", "1 entry per account"),
    ], default="account", required=True)

    single_date = fields.Date(string="Single entry date")
    single_journal_id = fields.Many2one("account.journal", string="Single entry journal")

    @api.constrains('closing_grouping', 'move_config_ids')
    def _check_single_grouping(self):
        for closing in self:
            if closing.closing_grouping == 'single' and len(closing.move_config_ids.filtered("enabled")) <= 1:
                raise ValidationError(_(
                    "The '1 entry per type' option requires more than one "
                    "enabled configuration in the moves configuration tab."
                ))

    @api.constrains('closing_grouping', 'move_config_ids')
    def _check_inverse_config_grouping(self):
        for closing in self:
            if closing.closing_grouping != 'config':
                for config in closing.move_config_ids:
                    if config.inverse_config_id:
                        raise ValidationError(_(
                            "Opening entries (Reverse entry from) are only allowed "
                            "when closing grouping is set to '1 entry per configuration'."
                        ))

    @api.constrains('year', 'company_id', 'state')
    def _check_unique_year_company(self):
        for record in self:
            if record.year and record.company_id:
                dup = self.search([
                    ('year', '=', record.year),
                    ('company_id', '=', record.company_id.id),
                    ('state', '=', 'posted'),
                    ('id', '!=', record.id),
                ])
                if dup:
                    raise ValidationError(_(
                        "There should be only one fiscal year closing "
                        "for that year and company!"
                    ))

    @api.constrains('date_start', 'date_end', 'date_opening', 'company_id')
    def _check_dates_consistency(self):
        for record in self:
            if not record.company_id.fiscalyear_last_month or not record.company_id.fiscalyear_last_day:
                raise ValidationError(_(
                    "Fiscal year end (month/day) must be configured on the company "
                    "before creating a fiscal year closing."
                ))
            lm = int(record.company_id.fiscalyear_last_month)
            ld = int(record.company_id.fiscalyear_last_day)
            if record.date_start and record.date_end:
                if record.date_start > record.date_end:
                    raise ValidationError(_("Start date cannot be later than end date."))
            if record.date_end and record.date_opening:
                if record.date_opening != record.date_end + relativedelta(days=1):
                    raise ValidationError(_("Opening date must be the day after end date."))
            if record.date_end and record.year and record.year != record.date_end.year:
                raise ValidationError(_(
                    "The fiscal year (%s) must match the end date year (%s)."
                ) % (record.year, record.date_end.year))
            if record.date_end:
                expected_end = date(record.date_end.year, lm, ld)
                if record.date_end != expected_end:
                    raise ValidationError(_(
                        "End date must be %s-%s-%s based on company's fiscal year configuration."
                    ) % (record.date_end.year, lm, ld))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        needs = any(f in fields_list for f in ['date_start', 'date_end', 'date_opening', 'year'])
        if not needs or (res.get('year') and res.get('date_start') and res.get('date_end')):
            return res
        company = self.env.company
        prev = False
        if not res.get('year'):
            prev = self.search([
                ('company_id', '=', company.id),
                ('state', '=', 'posted'),
            ], order='date_end desc', limit=1)
            if prev:
                res['year'] = prev.year + 1
            else:
                lm = int(company.fiscalyear_last_month or 12)
                ld = int(company.fiscalyear_last_day or 31)
                today = fields.Date.today()
                fy_start = date(today.year - 1 if today.month < lm or (today.month == lm and today.day < ld) else today.year, lm, ld) + relativedelta(days=1)
                if today >= fy_start:
                    res['year'] = today.year
                else:
                    res['year'] = today.year
        if not res.get('date_end') and res.get('year'):
            res['date_end'] = date(res['year'], int(company.fiscalyear_last_month or 12),
                                   int(company.fiscalyear_last_day or 31))
        if not res.get('date_start'):
            if prev:
                res['date_start'] = prev.date_opening
            else:
                lm = int(company.fiscalyear_last_month or 12)
                ld = int(company.fiscalyear_last_day or 31)
                res['date_start'] = date(res['year'] - 1, lm, ld) + relativedelta(days=1)
        if res.get('date_end') and not res.get('date_opening'):
            res['date_opening'] = res['date_end'] + relativedelta(days=1)
        return res

    @api.onchange('year')
    def _onchange_year(self):
        if self.year and self.company_id:
            company = self.company_id
            if not company.fiscalyear_last_month or not company.fiscalyear_last_day:
                raise ValidationError(_(
                    "Fiscal year end month and day must be set on the company. "
                    "Go to Accounting > Configuration > Settings."
                ))
            lm = int(company.fiscalyear_last_month)
            ld = int(company.fiscalyear_last_day)
            self.date_start = date(self.year - 1, lm, ld) + relativedelta(days=1)
            self.date_end = date(self.year, lm, ld)
            self.date_opening = self.date_end + relativedelta(days=1)

    @api.onchange('date_start')
    def _onchange_date_start(self):
        if self.date_start and self.company_id:
            company = self.company_id
            lm = int(company.fiscalyear_last_month or 12)
            ld = int(company.fiscalyear_last_day or 31)
            if (self.date_start.month < lm) or (self.date_start.month == lm and self.date_start.day <= ld):
                self.date_end = date(self.date_start.year, lm, ld)
            else:
                self.date_end = date(self.date_start.year + 1, lm, ld)
            self.date_opening = self.date_end + relativedelta(days=1)

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
                msg = _("One or more unposted moves found: \n")
                for move in draft_moves:
                    msg += "ID: %s, Date: %s, Number: %s, Ref: %s\n" % (
                        move.id,
                        move.date,
                        move.name,
                        move.ref,
                    )
                raise ValidationError(msg)
        return True

    def _moves_remove(self):
        for closing in self:
            for move in closing.move_ids:
                if move.state == 'posted':
                    move.button_draft()
                move.write({'fyc_id': False})
                move.button_cancel()
        return True

    def button_post(self):
        for closing in self:
            company = closing.company_id
            if company.fiscalyear_lock_date and closing.date_end <= company.fiscalyear_lock_date:
                company.sudo().fiscalyear_lock_date = False
            closing.move_ids.action_post()
            company.sudo().fiscalyear_lock_date = closing.date_end
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

    def _create_move_from_group(self, group):
        dest = self._get_dest_account()
        src_lines = []
        total = 0.0
        total_fb = 0.0
        for bal in group["lines"]:
            b = bal.get("balance", 0.0)
            if abs(b) < 1e-6:
                continue
            fb = bal.get("foreign_balance", 0.0)
            aid = bal["account_id"]
            if isinstance(aid, (list, tuple)):
                aid = aid[0]
            src_lines.append(Command.create({
                "account_id": aid,
                "currency_id": self.env.company.currency_id.id,
                "amount_currency": -b,
                "foreign_debit": fb if fb > 0 else 0.0,
                "foreign_credit": -fb if fb < 0 else 0.0,
                "not_foreign_recalculate": True,
                "name": bal["config"].name,
                "date": group["date"],
            }))
            total += b
            total_fb += fb
        if not src_lines:
            return
        all_lines = src_lines + [Command.create({
            "account_id": dest.id,
            "currency_id": self.env.company.currency_id.id,
            "amount_currency": total,
            "foreign_debit": total_fb if total_fb > 0 else 0.0,
            "foreign_credit": -total_fb if total_fb < 0 else 0.0,
            "not_foreign_recalculate": True,
            "name": _("Result"),
            "date": group["date"],
        })]
        mv = self._prepare_move_vals_from_group(group, all_lines)
        move = self.env["account.move"].create(mv)

    def _check_move_config_dates(self):
        for closing in self:
            for config in closing.move_config_ids.filtered("enabled"):
                if not config.date:
                    continue
                if config.date < closing.date_start or config.date > closing.date_end:
                    raise ValidationError(_(
                        "Config date '%s' for '%s' is outside "
                        "the fiscal year closing date range (%s - %s)."
                    ) % (config.date, config.name, closing.date_start, closing.date_end))

    def _check_duplicate_accounts_in_configs(self):
        for closing in self:
            configs = closing.move_config_ids.filtered("enabled")
            if len(configs) < 2:
                continue
            resolved = {}
            for config in configs:
                accounts = self.env["account.account"]
                for mapping in config.mapping_ids:
                    accounts |= accounts.search([
                        ("company_ids", "in", closing.company_id.ids),
                        ("code", "=ilike", mapping.src_accounts),
                    ])
                resolved[config] = accounts
            config_list = list(resolved.keys())
            for i in range(len(config_list)):
                for j in range(i + 1, len(config_list)):
                    c1, c2 = config_list[i], config_list[j]
                    overlap = resolved[c1] & resolved[c2]
                    if overlap:
                        codes = ", ".join(overlap.mapped("code"))
                        raise ValidationError(_(
                            "Configurations '%s' and '%s' share "
                            "source accounts: %s. They cannot have "
                            "overlapping source accounts."
                        ) % (c1.name, c2.name, codes))

    def calculate(self):
        self._check_move_config_dates()
        self._check_duplicate_accounts_in_configs()

        for closing in self:
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
        for balance_dict in balances:
            balance = balance_dict.get("balance", 0.0)

            # --- FILTRO: Solo moneda nativa ---
            if balance == 0:
                continue

   
            line_vals_list = []

            line_vals_list.append(Command.create({
                 
                    "account_id": balance_dict["account_id"][0],
                    "currency_id": self.env.company.currency_id.id,
                    "amount_currency": -balance,
                    "name": config.name,
                    "date": config.date,
                
            }))

            line_vals_list.append(Command.create({
                 
                    "currency_id": self.env.company.currency_id.id,
                    "account_id": dest_account.id,
                    "amount_currency": balance,
                    "name": _("Result"),
                    "date": config.date,
            }))

            self.env["account.move"].create({
                "ref": config.name,
                "date": config.date,
                "fyc_id": self.id,
                "move_type": 'entry',
                "closing_type": config.move_type,
                "journal_id": config.journal_id.id,
                "manually_set_rate": False,
                "line_ids": line_vals_list,
            })

          

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
            ("account_id", "=", account.id),
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
