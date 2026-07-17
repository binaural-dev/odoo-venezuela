import logging

from odoo import fields
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.common import TestPoSCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_pos")
class TestPosSessionForeignClose(TestPoSCommon):
    """Regresión: al cerrar una sesión con dos métodos de pago cash, uno de
    ellos con cuenta por cobrar intermediaria (tipo distinto a
    asset_receivable), `set_foreign_amount_in_line` escribía el monto foráneo
    del otro método sobre la línea de la cuenta intermediaria del asiento de
    cierre, dejando una línea con foreign_debit y foreign_credit a la vez y
    descuadrando la suma foránea del asiento (caso POSS/2026/0140 y
    POSS/2026/0085 de vzla17_farma).
    """

    FOREIGN_RATE = 36.0

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
        # Sin ref explícita _guess_chart_template puede resolver a un plan
        # contable cuyo módulo no está instalado (p.e. l10n_ve) y los tests
        # no pueden instalar módulos.
        super().setUpClass(chart_template_ref=chart_template_ref or "generic_coa")

        # l10n_ve_stock añade company_id + regla multicompañía a las
        # categorías; las del setup quedan en la compañía principal y el
        # usuario de test opera en las compañías de test.
        cls.env["product.category"].sudo().search([]).write({"company_id": False})

        cls.foreign_currency = cls.env.ref("base.VEF")
        cls.foreign_currency.active = True
        cls.company.currency_foreign_id = cls.foreign_currency
        cls.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "currency_id": cls.foreign_currency.id,
                "company_id": cls.company.id,
                "company_rate": cls.FOREIGN_RATE,
            }
        )

        cls.config = cls.basic_config

        # Cuenta intermediaria como cuenta por cobrar del método de pago,
        # igual que "Efectivo $"/"PdV" en producción: NO es asset_receivable.
        cls.intermediary_account = cls.env["account.account"].create(
            {
                "name": "USD - Cuenta Intermediaria (POS)",
                "code": "X1014.POS",
                "account_type": "asset_current",
                "reconcile": True,
            }
        )
        cash_journal_usd = cls.env["account.journal"].create(
            {
                "name": "Cash USD Test",
                "type": "cash",
                "code": "CSHUS",
                "company_id": cls.company.id,
            }
        )
        cls.cash_pm_intermediary = cls.cash_pm1.copy(
            default={
                "name": "Efectivo $ (intermediaria)",
                "journal_id": cash_journal_usd.id,
                "receivable_account_id": cls.intermediary_account.id,
            }
        )
        cls.config.write(
            {"payment_method_ids": [(4, cls.cash_pm_intermediary.id)]}
        )

        cls.product_a = cls.create_product("Producto Test", cls.categ_basic, 100.0)
        cls.adjust_inventory([cls.product_a], [10])

    def _add_foreign_ui_fields(self, order_data, foreign_amounts=None):
        """Inyecta los campos foráneos que la UI del PoS venezolano envía y
        que `_order_fields`/`_payment_fields` de l10n_ve_pos exigen.

        `foreign_amounts` permite forzar montos foráneos por pago que no
        coinciden exactamente con monto × tasa, como hace la UI real al
        redondear el precio unitario foráneo a 2 decimales por línea.
        """
        rate = self.FOREIGN_RATE
        data = order_data["data"]
        payments = [command[2] for command in data["statement_ids"]]
        for index, payment_vals in enumerate(payments):
            if foreign_amounts is not None:
                payment_vals["foreign_amount"] = foreign_amounts[index]
            else:
                payment_vals["foreign_amount"] = round(
                    payment_vals["amount"] * rate, 2
                )
            payment_vals["foreign_rate"] = rate
        data["foreign_amount_total"] = sum(p["foreign_amount"] for p in payments)
        data["foreign_currency_rate"] = rate
        data["foreign_inverse_rate"] = rate
        return order_data

    def test_close_session_intermediary_account_foreign_balance(self):
        """Orden facturada pagada con dos métodos cash (uno con cuenta
        intermediaria). Al cerrar, ninguna línea del asiento de cierre debe
        tener foreign_debit y foreign_credit simultáneamente, y la suma
        foránea debe cuadrar."""
        self.open_new_session()

        order_data = self._add_foreign_ui_fields(
            self.create_ui_order_data(
                [(self.product_a, 1)],
                customer=self.customer,
                is_invoiced=True,
                payments=[
                    (self.cash_pm_intermediary, 97.0),
                    (self.cash_pm1, 3.0),
                ],
            )
        )
        self.env["pos.order"].create_from_ui([order_data])

        session = self.pos_session
        cash_pm = session.payment_method_ids.filtered("is_cash_count")[:1]
        counted_cash = sum(
            session.order_ids.payment_ids.filtered(
                lambda p: p.payment_method_id == cash_pm
            ).mapped("amount")
        )
        session.post_closing_cash_details(counted_cash)
        session.close_session_from_ui()

        self.assertEqual(session.state, "closed")
        closing_move = session.move_id
        self.assertTrue(closing_move.line_ids)

        offending_lines = closing_move.line_ids.filtered(
            lambda l: l.foreign_debit > 0 and l.foreign_credit > 0
        )
        self.assertFalse(
            offending_lines,
            "Ninguna línea del asiento de cierre debe tener foreign_debit y "
            "foreign_credit a la vez. Líneas: %s"
            % offending_lines.mapped(
                lambda l: (l.account_id.code, l.foreign_debit, l.foreign_credit)
            ),
        )
        self.assertAlmostEqual(
            sum(closing_move.line_ids.mapped("foreign_debit")),
            sum(closing_move.line_ids.mapped("foreign_credit")),
            places=2,
            msg="El asiento de cierre debe cuadrar en moneda foránea.",
        )

        # La línea de la cuenta intermediaria solo debe llevar su propio
        # monto foráneo (97 * tasa), nunca el del otro método de pago.
        intermediary_line = closing_move.line_ids.filtered(
            lambda l: l.account_id == self.intermediary_account
        )
        self.assertEqual(len(intermediary_line), 1)
        self.assertAlmostEqual(
            intermediary_line.foreign_debit, 97.0 * self.FOREIGN_RATE, places=2
        )
        self.assertAlmostEqual(intermediary_line.foreign_credit, 0.0, places=2)

    def test_close_session_ui_rounded_foreign_amounts(self):
        """La UI del PoS calcula los montos foráneos redondeando el precio
        unitario foráneo a 2 decimales por línea, por lo que el monto foráneo
        del pago no coincide exacto con monto × tasa (caso POSS/2026/0172:
        21,08 de la UI vs 21,0606 por tasa). El asiento de cierre debe usar
        una sola fuente y cuadrar en moneda foránea de todas formas."""
        self.open_new_session()

        # 97 × 36 = 3492 exacto; la UI "manda" 3495 (deriva de redondeo por
        # línea). 3 × 36 = 108 exacto para el otro método.
        order_data = self._add_foreign_ui_fields(
            self.create_ui_order_data(
                [(self.product_a, 1)],
                customer=self.customer,
                is_invoiced=True,
                payments=[
                    (self.cash_pm_intermediary, 97.0),
                    (self.cash_pm1, 3.0),
                ],
            ),
            foreign_amounts=[3495.0, 108.0],
        )
        self.env["pos.order"].create_from_ui([order_data])

        session = self.pos_session
        cash_pm = session.payment_method_ids.filtered("is_cash_count")[:1]
        counted_cash = sum(
            session.order_ids.payment_ids.filtered(
                lambda p: p.payment_method_id == cash_pm
            ).mapped("amount")
        )
        session.post_closing_cash_details(counted_cash)
        session.close_session_from_ui()

        closing_move = session.move_id
        for line in closing_move.line_ids:
            _logger.info(
                "LINEA CIERRE %s | debit=%s credit=%s fd=%s fc=%s nfr=%s",
                line.account_id.code,
                line.debit,
                line.credit,
                line.foreign_debit,
                line.foreign_credit,
                line.not_foreign_recalculate,
            )
        self.assertFalse(
            closing_move.line_ids.filtered(
                lambda l: l.foreign_debit > 0 and l.foreign_credit > 0
            )
        )
        self.assertAlmostEqual(
            sum(closing_move.line_ids.mapped("foreign_debit")),
            sum(closing_move.line_ids.mapped("foreign_credit")),
            places=2,
            msg="El asiento de cierre debe cuadrar en moneda foránea aunque "
            "los montos de la UI difieran de monto × tasa.",
        )
