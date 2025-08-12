import logging
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command

_logger = logging.getLogger(__name__)

@tagged("post_install", "-at_install", "l10n_ve_accountant")
class TestAccountant(TransactionCase):
    """Tests for invoice posting behaviour regarding the invoice date."""

    def setUp(self):
        super().setUp()

        # --- Monedas y compañía ---
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "currency_id": self.currency_usd.id,
            "currency_foreign_id": self.currency_vef.id,
        })

        # Tipo de cambio de referencia
        self.env['res.currency.rate'].create({
            'name': fields.Date.from_string('2025-07-28'),
            'currency_id': self.currency_usd.id,
            'inverse_company_rate': 120.439,
            'company_id': self.company.id,
        })

        # --- Journal bancario en USD (o se reutiliza uno existente) ---
        self.bank_journal_usd = (
            self.env['account.journal'].search(
                [("type", "=", "bank"), ("currency_id", "=", self.currency_usd.id), ("company_id", "=", self.company.id)],
                limit=1,
            )
            or self.env['account.journal'].create({
                "name": "Banco USD",
                "code": "BNKUS",
                "type": "bank",
                "currency_id": self.currency_usd.id,
                "company_id": self.company.id,
            })
        )

        # --- Payment Method Manual inbound (reusar, no crear) ---
        self.payment_method = (
            self.env['account.payment.method'].search([('code', '=', 'manual'), ('payment_type', '=', 'inbound')], limit=1)
            or self.env.ref('account.account_payment_method_manual_in')
        )

        # --- Payment Method Line en el journal de BANCO (no en ventas) ---
        self.pm_line_in_usd = (
            self.env["account.payment.method.line"].search(
                [
                    ("journal_id", "=", self.bank_journal_usd.id),
                    ("payment_method_id", "=", self.payment_method.id),
                ],
                limit=1,
            )
            or self.env["account.payment.method.line"].create({
                "journal_id": self.bank_journal_usd.id,
                "payment_method_id": self.payment_method.id,
            })
        )

        # --- Impuesto ---
        self.tax_iva16 = self.env['account.tax'].create({
            'name': 'IVA 16%',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'company_id': self.company.id,
        })

        # --- Producto / Partner ---
        self.product = self.env['product.product'].create({
            'name': 'Producto Prueba',
            'type': 'service',
            'list_price': 100,
            'barcode': '123456789',
            'taxes_id': [(6, 0, [self.tax_iva16.id])],
            'company_id': False,
        })

        self.partner_a = self.env['res.partner'].create({
            'name': 'Test Partner A',
            'customer_rank': 1,
            'company_id': False,
        })
        self.partner = self.partner_a  # usado por helpers

        # --- Journal de ventas (sin métodos de pago) ---
        self.sale_journal = (
            self.env['account.journal'].search([
                ('type', '=', 'sale'), ('company_id', '=', self.company.id)
            ], limit=1)
            or self.env['account.journal'].create({
                'name': 'Sales',
                'code': 'SAJT',  # evita colisiones con SAJ
                'type': 'sale',
                'company_id': self.company.id,
            })
        )

        # (Opcional) Si tu módulo de anticipos exige cuentas específicas:
        # Cuentas de anticipo en la compañía (tipos modernos v16/v17: account_type)
        if not getattr(self.company, 'advance_customer_account_id', False) or not getattr(self.company, 'advance_supplier_account_id', False):
            adv_cust = self.env['account.account'].search([('code', '=', '900000'), ('company_id', '=', self.company.id)], limit=1) or \
                self.env['account.account'].create({
                    'name': 'Advance Customers',
                    'code': '900000',
                    'account_type': 'liability_current',
                    'reconcile': True,
                    'company_id': self.company.id,
                })
            adv_supp = self.env['account.account'].search([('code', '=', '900001'), ('company_id', '=', self.company.id)], limit=1) or \
                self.env['account.account'].create({
                    'name': 'Advance Suppliers',
                    'code': '900001',
                    'account_type': 'asset_current',
                    'reconcile': True,
                    'company_id': self.company.id,
                })
            self.company.write({
                'advance_customer_account_id': adv_cust.id,
                'advance_supplier_account_id': adv_supp.id,
            })

        # Nota: eliminamos la creación previa de self.account_payment_method_line en el journal de VENTAS
        # y también evitamos crear un payment anticipado aquí que dispare la constraint antes del test.

    # ----------------- Helpers -----------------
    def _create_invoice(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.sale_journal.id,
            'date': fields.Date.today(),
            'invoice_line_ids': [
                Command.create({
                    'product_id': self.product.id,
                    'quantity': 1.0,
                    'price_unit': 100.0,
                })
            ],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    def _create_payment(
        self,
        amount,
        *,
        currency=None,
        journal=None,
        is_advance=False,
        fx_rate=None,
        fx_rate_inv=None,
        pm_line=None,
    ):
        """Crea y valida un payment genérico."""
        currency = currency or self.currency_usd
        journal = journal or self.bank_journal_usd
        pm_line = pm_line or self.pm_line_in_usd

        vals = {
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "amount": amount,
            "currency_id": currency.id,
            "journal_id": journal.id,
            "payment_method_line_id": pm_line.id,  # <-- misma línea y mismo journal
            "is_advance_payment": is_advance,
            "date": fields.Date.today(),
        }
        if fx_rate:
            vals.update({"foreign_rate": fx_rate, "foreign_inverse_rate": fx_rate_inv})

        pay = self.env["account.payment"].create(vals)
        pay.action_post()
        return pay

    # ----------------- Test -----------------
    def test_reconcile_twice(self):
        '''
        This test verifies that when an advance payment is unmatched from an invoice, it can be matched again if required.
        '''
        invoice = self._create_invoice()
        payment = self._create_payment(
            amount=invoice.amount_total,
            journal=self.bank_journal_usd,
            pm_line=self.pm_line_in_usd,
            is_advance=True,
        )
        #First reconciliation
        for line in payment.line_ids:
            line_ids = payment.line_ids.filtered(lambda line: line.account_type in ('asset_receivable', 'liability_payable', 'asset_current', 'liability_payable') and not line.reconciled)
        if not line_ids:
            _logger.warning("Theres not lines to conciliate")
        else:
            for line in line_ids:
                invoice.js_assign_outstanding_line(line.id)

        #Breaking reconciliation
        conciliation_move = self.env['account.move'].search([('move_type', '=', 'entry'), ('name', '=',f'{invoice.name} - {payment.name}') ])
        partial = self.env['account.partial.reconcile'].search([('debit_move_id.move_id', '=', invoice.id), ('credit_move_id.move_id', '=', conciliation_move.id),], limit=1)
        invoice.js_remove_outstanding_partial(partial.id)

        # Second reconciliation should not raise duplicate name error
        invoice.js_assign_outstanding_line(line.id)
        second_conciliation_move = self.env['account.move'].search([('move_type', '=', 'entry'), ('name', '=',f'{invoice.name} - {payment.name}'), ('state', '=', 'posted') ])
        second_conciliation_move and conciliation_move
        first_conciliation_move = self.env['account.move'].search([('move_type', '=', 'entry'), ('name', '=',f'{invoice.name} - {payment.name}'), ('state', '=', 'cancel') ])
        # It is evaluated whether the first journal entry with canceled state and the second with posted state are created.
        self.assertTrue(conciliation_move and first_conciliation_move)
