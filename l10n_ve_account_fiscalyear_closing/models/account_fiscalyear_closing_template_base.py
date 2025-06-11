# Copyright 2016 Tecnativa - Antonio Espinosa
# Copyright 2017 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountFiscalyearClosingTemplate(models.Model):
    _inherit = "account.fiscalyear.closing.abstract"
    _name = "account.fiscalyear.closing.template"
    _description = "Fiscal year closing template"

    name = fields.Char(translate=True)
    move_config_ids = fields.One2many(
        comodel_name="account.fiscalyear.closing.config.template",
        inverse_name="template_id",
        string="Moves configuration",
    )


class AccountFiscalyearClosingConfigTemplate(models.Model):
    _inherit = "account.fiscalyear.closing.config.abstract"
    _name = "account.fiscalyear.closing.config.template"
    _order = "sequence asc, id asc"
    _description = "Fiscal year closing configuration template"

    name = fields.Char(translate=True)
    template_id = fields.Many2one(
        comodel_name="account.fiscalyear.closing.template",
        index=True,
        readonly=True,
        string="Fiscal Year Closing Template",
        required=True,
        ondelete="cascade",
    )
    journal_id = fields.Many2one(company_dependent=True)
    mapping_ids = fields.One2many(
        comodel_name="account.fiscalyear.closing.mapping.template",
        inverse_name="template_config_id",
        string="Account mappings",
    )
    closing_type_ids = fields.One2many(
        comodel_name="account.fiscalyear.closing.type.template",
        inverse_name="template_config_id",
        string="Closing types",
    )
    move_date = fields.Selection(
        selection=[
            ("last_ending", "Last date of the ending period"),
            ("first_opening", "First date of the opening period"),
        ],
        string="Move date",
        default="last_ending",
        required=True,
    )
    l_map = fields.Boolean(string="Load accounts")

    @api.onchange("l_map")
    def inchange_l_map(self):
        accounts = (
            self.env["account.account"].sudo().search(
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
                    ("company_id", "in", [self.env.company.id, False]),
                ]
            )
        )
        config_a = (
            self.env["account.account"].sudo().search(
                [
                    ("account_type", "=", "equity_unaffected"),
                    ("company_id", "in", [self.env.company.id, False]),
                ],
                limit=1,
            )
        )
        maps = []
        if self.l_map:
            for a in accounts:
                if len(a.code):
                    vals = {
                        "name": a.name,
                        "src_accounts": a.code,
                        "dest_account": config_a.code,
                        "template_config_id": self.id,
                    }
                    maps.append((0, 0, vals))
            if maps:
                return {"value": {"mapping_ids": maps}}
        else:
            return {"value": {"mapping_ids": [(5, 0, 0)]}}

    _sql_constraints = [
        (
            "code_uniq",
            "unique(code, template_id)",
            "Code must be unique per fiscal year closing!",
        ),
    ]


class AccountFiscalyearClosingMappingTemplate(models.Model):
    _inherit = "account.fiscalyear.closing.mapping.abstract"
    _name = "account.fiscalyear.closing.mapping.template"
    _description = "Fiscal year closing mapping template"

    name = fields.Char(translate=True)
    template_config_id = fields.Many2one(
        comodel_name="account.fiscalyear.closing.config.template",
        index=True,
        string="Fiscal year closing config template",
        readonly=True,
        required=True,
        ondelete="cascade",
    )
    src_accounts = fields.Char(
        string="Source accounts",
        required=True,
        help="Account code pattern for the mapping source accounts",
    )
    dest_account = fields.Char(
        string="Destination account",
        help="Account code pattern for the mapping destination account. Only "
        "the first match will be considered. If this field is not "
        "filled, the performed operation will be to remove any existing "
        "balance on the source accounts with an equivalent counterpart "
        "in the same account.",
    )


class AccountFiscalyearClosingTypeTemplate(models.Model):
    _inherit = "account.fiscalyear.closing.type.abstract"
    _name = "account.fiscalyear.closing.type.template"
    _description = "Fiscal year closing type template"

    template_config_id = fields.Many2one(
        comodel_name="account.fiscalyear.closing.config.template",
        index=True,
        string="Fiscal year closing config template",
        readonly=True,
        required=True,
        ondelete="cascade",
    )
