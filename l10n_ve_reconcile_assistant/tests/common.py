from contextlib import contextmanager

from odoo import Command
from odoo.tests import Form

from odoo.addons.l10n_ve_igtf.tests.common_currency import CurrencyFixtureCommon


class ReconcileAssistantCommon(CurrencyFixtureCommon):
    """Fixture del asistente: la base de `CurrencyFixtureCommon` (compañía VEF con USD alterna, diarios de
    banco por moneda, impuestos exentos) más lo que necesita el IGTF: anticipos de clientes, cuenta y
    diario de cruces, diario de banco USD con IGTF, y socio y compañía formales."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        company_ids = [Command.set([cls.company.id])]
        cls.advance_account = env["account.account"].create({
            "name": "Anticipo Clientes Prueba Asistente", "code": "2160ASI",
            "account_type": "liability_current", "reconcile": True,
            "is_advance_account": True, "company_ids": company_ids,
        })
        cls.igtf_account = env["account.account"].create({
            "name": "IGTF Clientes Prueba Asistente", "code": "2361ASI",
            "account_type": "liability_current", "company_ids": company_ids,
        })
        cls.cross_journal = env["account.journal"].create({
            "name": "Cruces de anticipo Prueba Asistente", "type": "general",
            "code": "CRUAS", "company_id": cls.company.id,
        })
        cls.company.write({
            "taxpayer_type": "formal",
            "igtf_percentage": 3.0,
            "customer_account_igtf_id": cls.igtf_account.id,
            "advance_customer_account_id": cls.advance_account.id,
            "advance_payment_igtf_journal_id": cls.cross_journal.id,
        })
        cls.bank["USD"].is_igtf = True
        cls.partner.write({
            "vat": "J123456789", "taxpayer_type": "formal",
            "default_advance_customer_account_id": cls.advance_account.id,
        })
        cls.other_partner = env["res.partner"].create({
            "name": "Otro Cliente Prueba Asistente",
            "property_account_receivable_id": cls.acc_receivable.id,
            "property_account_payable_id": cls.acc_payable.id,
        })

    def _advance_payment(self, journal, amount, date=None, keep=False):
        """Anticipo de cliente posteado, creado con el formulario de pago; devuelve su línea en la
        cuenta de anticipos. `keep` marca "Mantener monto en valor alterno" (solo en pagos en Bs)."""
        if keep:
            self.env.user.group_ids |= self.env.ref("l10n_ve_igtf.revalorizate_vef_group")
        context = {
            "default_payment_type": "inbound", "default_partner_type": "customer",
            "default_is_advance_payment": True,
        }
        with Form(self.env["account.payment"].with_context(**context)) as form:
            form.partner_id = self.partner
            form.journal_id = journal
            form.amount = amount
            if date:
                form.date = date
            if keep:
                form.keep_alter_value_vef = True
        payment = form.save()
        payment.action_post()
        return payment.move_id.line_ids.filtered(lambda line: line.account_id.is_advance_account)

    def _vef_payment(self, amount, date, keep):
        """Pago recibido en Bs creado con el formulario, con "Mantener monto en valor alterno" como lo
        marcaría el usuario (el campo solo lo ve el grupo de revalorización); devuelve su línea por cobrar."""
        self.env.user.group_ids |= self.env.ref("l10n_ve_igtf.revalorizate_vef_group")
        context = {"default_payment_type": "inbound", "default_partner_type": "customer"}
        with Form(self.env["account.payment"].with_context(**context)) as form:
            form.partner_id = self.partner
            form.journal_id = self.bank["VEF"]
            form.amount = amount
            form.date = date
            form.keep_alter_value_vef = keep
        payment = form.save()
        payment.action_post()
        return payment.move_id.line_ids.filtered(lambda line: line.account_type == "asset_receivable")

    @contextmanager
    def _active_company(self, company):
        """El usuario trabaja con `company` como compañía activa (sigue teniendo la principal habilitada)."""
        env = self.env
        self.env.user.company_ids |= company
        self.env = env(context=dict(env.context, allowed_company_ids=[company.id, self.company.id]))
        try:
            yield
        finally:
            self.env = env

    def _receivable_line(self, invoice):
        return invoice.line_ids.filtered(lambda line: line.account_type == "asset_receivable")

    def _entry_line(self, account, debit, credit, partner=None, is_advance_move=False, post=True):
        """Línea de un asiento manual en `account` (con su contrapartida en un diario general)."""
        counterpart = self.acc_payable if account == self.acc_receivable else self.acc_receivable
        entry = self.env["account.move"].create({
            "move_type": "entry", "journal_id": self.cross_journal.id, "date": "2026-08-01",
            "is_advance_move": is_advance_move,
            "line_ids": [
                Command.create({"account_id": account.id, "debit": debit, "credit": credit,
                                "partner_id": (partner or self.partner).id}),
                Command.create({"account_id": counterpart.id, "debit": credit, "credit": debit,
                                "partner_id": (partner or self.partner).id}),
            ],
        })
        if post:
            entry.action_post()
        return entry.line_ids.filtered(lambda line: line.account_id == account)

    def _open_assistant(self, lines):
        """Abre el asistente sobre `lines` con el formulario, como el botón Reconciliar, y lo guarda."""
        action = lines.action_l10n_ve_reconcile_assistant()
        with Form.from_action(self.env, action) as form:
            pass
        return form.save()
