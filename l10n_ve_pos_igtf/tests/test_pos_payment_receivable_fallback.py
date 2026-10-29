import logging

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.common import TestPoSCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_pos_igtf")
class TestPosPaymentReceivableFallback(TestPoSCommon):
    """Ticket #15968: un cliente sin cuenta por cobrar/por pagar propia en la
    compañía (p.e. un contacto creado al vuelo desde el POS) hacía que
    `_create_payment_moves` intentara crear la línea de crédito del pago sin
    `account_id`. PostgreSQL rechazaba el insert por el CHECK CONSTRAINT
    `account_move_line_check_accountable_required_fields` y abortaba toda la
    transacción, mostrando solo "current transaction is aborted" sin indicar
    la causa real.
    """

    @classmethod
    def setup_company_data(cls, company_name, chart_template=None, **kwargs):
        # Corre antes de que AccountTestInvoicingCommon cree product_b (dos
        # impuestos de la misma compañía), que dispara el constraint
        # _check_taxes_id de l10n_ve_stock. Se desactiva solo durante esta
        # clase de test.
        cls._disable_ve_single_tax_constraint()
        return super().setup_company_data(
            company_name, chart_template=chart_template, **kwargs
        )

    @classmethod
    def _disable_ve_single_tax_constraint(cls):
        if getattr(cls, "_ve_tax_constraint_patched", False):
            return
        cls._ve_tax_constraint_patched = True
        template_cls = cls.env.registry["product.template"]
        original = cls.env["product.template"]._constraint_methods
        template_cls._constraint_methods = [
            method
            for method in original
            if getattr(method, "__name__", "") != "_check_taxes_id"
        ]
        cls.addClassCleanup(setattr, template_cls, "_constraint_methods", original)

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref or "generic_coa")

        # l10n_ve_stock añade company_id + regla multicompañía a las
        # categorías; las del setup quedan en la compañía principal y el
        # usuario de test opera en las compañías de test.
        cls.env["product.category"].sudo().search([]).write({"company_id": False})

        cls.config = cls.basic_config
        # action_pos_session_open (l10n_ve_pos_igtf) exige la cuenta IGTF de
        # la compañía configurada para poder abrir la sesión, aunque los
        # pagos de este test no incluyan IGTF.
        cls.company.customer_account_igtf_id = cls.env["account.account"].create(
            {
                "name": "IGTF por Cobrar",
                "code": "X1013.IGTF",
                "account_type": "asset_current",
            }
        )
        # _action_to_open_ui (l10n_ve_pos) exige una moneda extranjera activa
        # configurada en la compañía para poder abrir la sesión.
        foreign_currency = cls.env.ref("base.VEF")
        foreign_currency.active = True
        cls.company.currency_foreign_id = foreign_currency
        cls.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "currency_id": foreign_currency.id,
                "company_id": cls.company.id,
                "company_rate": 36.0,
            }
        )
        cls.product_a = cls.env["product.product"].create(
            {
                "name": "Producto Test IGTF",
                "available_in_pos": True,
                "list_price": 25.61,
                "taxes_id": [(5, 0, 0)],
            }
        )
        # Contacto sin cuenta por cobrar/por pagar propia, igual que uno
        # creado al vuelo desde el POS.
        cls.pos_customer_no_account = cls.env["res.partner"].create(
            {"name": "Cliente creado desde POS"}
        )
        # El chart template de prueba (generic_coa) deja un default
        # compañía-wide de property_account_receivable_id/_payable_id que
        # cualquier partner heredaría. Se fuerza un override vacío solo para
        # este partner, igual que un contacto real creado desde el POS sin
        # pasar por el formulario de Contactos.
        cls.pos_customer_no_account.write(
            {
                "property_account_receivable_id": False,
                "property_account_payable_id": False,
            }
        )

    FOREIGN_RATE = 36.0

    def _add_foreign_ui_fields(self, order_data):
        """Inyecta los campos foráneos que la UI real del PoS venezolano
        envía y que `_order_fields`/`_payment_fields` de l10n_ve_pos exigen.
        """
        data = order_data["data"]
        payments = [command[2] for command in data["statement_ids"]]
        for payment_vals in payments:
            payment_vals["foreign_amount"] = round(
                payment_vals["amount"] * self.FOREIGN_RATE, 2
            )
            payment_vals["foreign_rate"] = self.FOREIGN_RATE
            payment_vals["include_igtf"] = False
            payment_vals["igtf_amount"] = 0
            payment_vals["foreign_igtf_amount"] = 0
        data["foreign_amount_total"] = sum(p["foreign_amount"] for p in payments)
        data["foreign_currency_rate"] = self.FOREIGN_RATE
        data["foreign_inverse_rate"] = self.FOREIGN_RATE
        data["igtf_amount"] = 0
        return order_data

    def test_payment_falls_back_to_company_default_receivable_account(self):
        """Si el partner no tiene cuenta por cobrar propia, se debe usar la
        cuenta por cobrar por defecto de la compañía en vez de abortar la
        transacción."""
        self.open_new_session()
        order_data = self._add_foreign_ui_fields(
            self.create_ui_order_data(
                [(self.product_a, 1)],
                customer=self.pos_customer_no_account,
                is_invoiced=True,
                payments=[(self.cash_pm1, 25.61)],
            )
        )
        self.env["pos.order"].create_from_ui([order_data])

        order = self.pos_session.order_ids.filtered(
            lambda o: o.partner_id == self.pos_customer_no_account
        )
        self.assertTrue(order, "La orden debió crearse e invoicearse sin error.")
        payment_move = order.payment_ids.account_move_id
        self.assertTrue(payment_move)
        receivable_line = payment_move.line_ids.filtered(
            lambda l: l.account_id == self.pos_receivable_account
        )
        self.assertTrue(
            receivable_line,
            "La línea de crédito del pago debió usar la cuenta por cobrar "
            "por defecto de la compañía "
            "(account_default_pos_receivable_account_id).",
        )

    def test_payment_without_any_receivable_account_raises_user_error(self):
        """Si tampoco hay cuenta por cobrar por defecto en la compañía, debe
        mostrarse un UserError claro en vez de dejar que PostgreSQL aborte la
        transacción con un mensaje genérico."""
        self.open_new_session()
        self.company.account_default_pos_receivable_account_id = False

        order_data = self._add_foreign_ui_fields(
            self.create_ui_order_data(
                [(self.product_a, 1)],
                customer=self.pos_customer_no_account,
                is_invoiced=True,
                payments=[(self.cash_pm1, 25.61)],
            )
        )
        with self.assertRaises(UserError):
            self.env["pos.order"].create_from_ui([order_data])
