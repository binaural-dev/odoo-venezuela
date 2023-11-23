from odoo import fields, models


class AccountFiscalYearClosingUnbalancedMove(models.TransientModel):
    _name = 'account.fiscalyear.closing.unbalanced.move'
    _description = 'Account fiscalyear closing unbalanced move'

    journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Diario",
        readonly=True,
    )
    ref = fields.Char(
        string="Referencia",
        readonly=True,
    )
    date = fields.Date(
        string="Fecha",
        readonly=True,
    )
    line_ids = fields.One2many(
        comodel_name='account.fiscalyear.closing.unbalanced.move.line',
        inverse_name='move_id',
        string="Líneas de movimiento desequilibradas",
        readonly=True,
    )
    foreign_currency_rate = fields.Float(string='Tasa')


class AccountFiscalYearClosingUnbalancedMoveLine(models.TransientModel):
    _name = 'account.fiscalyear.closing.unbalanced.move.line'
    _description = 'Account fiscalyear closing unbalanced move line'

    move_id = fields.Many2one(
        comodel_name='account.fiscalyear.closing.unbalanced.move',
        string="Movimiento desequilibrado",
    )
    account_id = fields.Many2one(
        comodel_name='account.account',
        string="Cuenta",
    )
    credit = fields.Float()
    debit = fields.Float()
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Socio",
    )
    name = fields.Char()
    date = fields.Date(string='fecha')
