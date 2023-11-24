from odoo import fields, models, api


class AccountFiscalyearClosingAbstract(models.AbstractModel):
    _name = "account.fiscalyear.closing.abstract"
    _description = "Account fiscalyear closing abstract"

    name = fields.Char(string="Description", required=True)
    company_id = fields.Many2one('res.company',ondelete='cascade',)
    check_draft_moves = fields.Boolean(
        default=True,
        help="Checks that there are no draft moves on the fiscal year "
             "that is being closed. Non-confirmed moves won't be taken in "
             "account on the closing operations.",
    )


class AccountFiscalyearClosingConfigAbstract(models.AbstractModel):
    _name = "account.fiscalyear.closing.config.abstract"
    _description = "Account fiscalyear closing config abstract"
    _order = "sequence asc, id asc"

    name = fields.Char(string="Description", required=True)
    sequence = fields.Integer(index=True, default=1)
    code = fields.Char(string="Uni Code", required=True)
    inverse = fields.Char(
        string="Inverse Configuration",
        help="Configuration code to inverse its move",
    )
    move_type = fields.Selection(
        selection=[
            ('closing', 'Closing'),
            ('opening', 'Opening'),
            ('loss_profit', 'Profit and Lost'),
            ('other', 'Other'),
        ], string="Move type", default='closing',
    )
    journal_id = fields.Many2one("account.journal")
    closing_type_default = fields.Selection(
        selection=[
            ('balance', 'Balance'),
            ('unreconciled', 'Unreconciled'),
        ], string="Default closure type", required=True, default='balance',
    )


class AccountFiscalyearClosingMappingAbstract(models.AbstractModel):
    _name = "account.fiscalyear.closing.mapping.abstract"
    _description = "Account fiscalyear closing mapping abstract"

    name = fields.Char(string="Description")


class AccountFiscalyearClosingTypeAbstract(models.AbstractModel):
    _name = "account.fiscalyear.closing.type.abstract"
    _description = "Account fiscalyear closing type abstract"

    closing_type_default = fields.Selection(
        selection=[
            ('balance', 'Balance'),
            ('unreconciled', 'Unreconciled'),
        ], string="Default closure type", required=True,
        default='unreconciled',
    )
    #account_type_id
    account_type = fields.Selection(
        selection='_get_fields_account_type',
        required=True,
    )

    @api.model
    def _get_fields_account_type(self):
        account_type = self.env["account.account"]._fields['account_type'].selection
        return account_type
