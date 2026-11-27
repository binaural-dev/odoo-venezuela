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
        """Un método en una tercera moneda no es el de la moneda de la
        compañía ni un método ``is_foreign_currency`` (el de la alterna, que
        tiene su propio flujo). Sus dos diarios de cruce son obligatorios: su
        diario es el transitorio en la moneda de la caja y los euros solo
        llegan a la caja real con el cruce (``_is_cross_move_eligible`` omite en
        silencio un método sin ellos). Su diario real (``cross_journal``) lleva
        esa moneda, porque el cruce le pone ``amount_currency`` en ella.

        Lo que depende de la caja (su moneda, la alterna) lo valida cada caja
        del método (``pos.config._get_tender_currency_error``).
        """
        for method in self.filtered("tender_currency_id"):
            company = method.company_id
            currency = method.tender_currency_id
            if method.is_foreign_currency:
                raise ValidationError(_(
                    "The payment method %(method)s cannot be a foreign currency method and have a "
                    "tender currency at the same time: the foreign currency method is always "
                    "collected in %(foreign)s.",
                    method=method.name,
                    foreign=company.foreign_currency_id.name,
                ))
            if currency == company.currency_id:
                raise ValidationError(method._tender_currency_not_third_message())
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
            for config in method.config_ids:
                config._check_tender_currency_methods(method)

    @api.constrains("is_foreign_currency", "tender_currency_id", "journal_id", "cross_journal")
    def _check_distinct_suspense_accounts(self):
        """Un método en moneda alterna (``is_foreign_currency``) o con tercera
        moneda de cobro (``tender_currency_id``) mueve el dinero de su diario
        transitorio (``journal_id``) al real (``cross_journal``) con el
        asiento de cruce. Si los dos diarios comparten la cuenta transitoria, el
        cruce queda en la misma cuenta y el dinero nunca pasa de un diario al
        otro, así que cada uno debe tener la suya.
        """
        for method in self.filtered(lambda m: m.is_foreign_currency or m.tender_currency_id):
            account = method.journal_id.suspense_account_id
            if account and account == method.cross_journal.suspense_account_id:
                raise ValidationError(_(
                    "The journal %(journal)s and the cross journal %(cross_journal)s of the "
                    "payment method %(method)s use the same suspense account %(account)s. Each "
                    "journal must have its own suspense account.",
                    journal=method.journal_id.display_name,
                    cross_journal=method.cross_journal.display_name,
                    method=method.name,
                    account=account.display_name,
                ))

    @api.constrains("journal_id", "config_ids")
    def _check_journal_currency_in_pos(self):
        """El diario de un método con moneda tiene que estar en la moneda de
        cada caja del método. Es la regla del core (``pos.config._check_currencies``),
        que solo se revisa al guardar la caja o al abrirla: aquí también se
        revisa al guardar el método, para no esperar a la apertura (ticket 15399).
        Un diario sin moneda se permite: trabaja en la moneda de la compañía (en
        una caja en otra moneda es el cobro en esa moneda, ver
        ``binaural_pos_multicurrency``).

        Un método sin caja no se valida: se valida cuando se le asigna una,
        desde aquí o desde la caja. Tampoco se le exige la moneda de la compañía
        a un método en moneda alterna o con moneda de cobro: en una caja en
        otra moneda, ``binaural_pos_multicurrency`` cobra la moneda de cobro con
        un diario transitorio en la moneda de la caja.
        """
        for method in self:
            journal_currency = method.journal_id.currency_id
            if not journal_currency:
                continue
            configs = method.config_ids.filtered(lambda c: c.currency_id != journal_currency)
            if configs:
                raise ValidationError(_(
                    "The journal %(journal)s of the payment method %(method)s is in "
                    "%(journal_currency)s, but the Point of Sale %(pos)s works in "
                    "%(pos_currency)s. The journal of a payment method must be in the currency "
                    "of its Point of Sale.",
                    journal=method.journal_id.display_name,
                    method=method.name,
                    journal_currency=journal_currency.name,
                    pos=configs[0].name,
                    pos_currency=configs[0].currency_id.name,
                ))

    def _tender_currency_not_third_message(self):
        return _(
            "The tender currency of the payment method %(method)s must be a third "
            "currency: %(currency)s is the company currency or its foreign currency.",
            method=", ".join(self.mapped("name")),
            currency=", ".join(self.tender_currency_id.mapped("name")),
        )

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
