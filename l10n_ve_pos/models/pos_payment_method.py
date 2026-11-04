from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    is_foreign_currency = fields.Boolean(default=False)

    tender_currency_id = fields.Many2one(
        "res.currency",
        string="Third Tender Currency",
        domain=[("active", "=", True)],
        help="Third currency the customer pays in with this method (e.g. EUR in a PoS in Bs with "
        "USD as foreign currency). The cashier types the amount in this currency and the PoS "
        "converts it to its own currency at the rate of the day. The journal of the method is the "
        "transitory one in the PoS currency and the Cross Journal is the real one in this currency. "
        "Leave it empty for methods in the PoS currency or in the foreign currency "
        "(Is Foreign Currency).",
    )

    cross_account_journal = fields.Many2one("account.journal", domain=[("type", "=", "general")])

    cross_journal = fields.Many2one("account.journal", domain=[("type", "in", ("bank", "cash"))])

    @api.constrains(
        "tender_currency_id", "is_foreign_currency", "journal_id", "cross_journal",
        "cross_account_journal", "company_id", "config_ids",
    )
    def _check_tender_currency(self):
        """Un método en una tercera moneda no es el de la moneda de la caja ni
        el de la alterna: cada uno tiene su propio flujo (``is_foreign_currency``
        para la alterna). Sus dos diarios de cruce son obligatorios: su diario
        es el transitorio en la moneda de la caja y los euros solo llegan a la
        caja real con el cruce (``_is_cross_move_eligible`` omite en silencio un
        método sin ellos). Su diario real (``cross_journal``) lleva esa moneda,
        porque el cruce le pone ``amount_currency`` en ella. Y solo se usa en
        cajas en la moneda de la compañía (ver
        ``pos.config._check_tender_currency_methods_currency``).
        """
        for method in self.filtered("tender_currency_id"):
            company = method.company_id
            currency = method.tender_currency_id
            if any(config.currency_id != config.company_id.currency_id for config in method.config_ids):
                raise ValidationError(method._tender_currency_in_foreign_pos_message())
            if method.is_foreign_currency:
                raise ValidationError(_(
                    "The payment method %(method)s cannot be a foreign currency method and have a "
                    "tender currency at the same time: the foreign currency method is always "
                    "collected in %(foreign)s.",
                    method=method.name,
                    foreign=company.foreign_currency_id.name,
                ))
            if currency in (company.currency_id | company.foreign_currency_id):
                raise ValidationError(_(
                    "The tender currency of the payment method %(method)s must be a third "
                    "currency: %(currency)s is the company currency or its foreign currency.",
                    method=method.name,
                    currency=currency.name,
                ))
            if method.type == "pay_later":
                raise ValidationError(_(
                    "The payment method %(method)s is a customer account: it cannot have a "
                    "tender currency.",
                    method=method.name,
                ))
            if not (method.cross_journal and method.cross_account_journal):
                raise ValidationError(_(
                    "The payment method %(method)s is collected in %(currency)s: set its Cross "
                    "Journal (the real journal in %(currency)s) and its Cross Account Journal.",
                    method=method.name,
                    currency=currency.name,
                ))
            if method.cross_journal.currency_id != currency:
                raise ValidationError(_(
                    "The cross journal %(journal)s of the payment method %(method)s must be in "
                    "%(currency)s, its tender currency.",
                    journal=method.cross_journal.display_name,
                    method=method.name,
                    currency=currency.name,
                ))

    def _tender_currency_in_foreign_pos_message(self):
        return _(
            "The payment method %(method)s is collected in %(currency)s and is used in a Point of "
            "Sale whose currency is not the company currency. A tender currency is only supported "
            "in a Point of Sale in the company currency.",
            method=", ".join(self.mapped("name")),
            currency=", ".join(self.tender_currency_id.mapped("name")),
        )

    @api.model
    def _load_pos_data_fields(self, config_id):
        res = super()._load_pos_data_fields(config_id)
        res += ['is_foreign_currency', 'cross_account_journal', 'cross_journal', 'tender_currency_id']
        return res
