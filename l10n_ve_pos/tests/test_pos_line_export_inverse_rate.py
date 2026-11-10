from odoo import fields
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged("post_install", "-at_install", "l10n_ve_pos")
class TestPosLineExportInverseRate(TestPoSCommon):
    """Regresión del ticket 15121: al recargar en el PoS una orden guardada como
    borrador, la línea solo recibía `foreign_currency_rate`, que en la orden es la
    tasa Bs/USD (get_display_rate). En compañías con base Bs, `get_rate()` la
    comparaba contra `init_conversion_rate` (tasa inversa), las tomaba por
    distintas y multiplicaba el precio por la tasa Bs/USD al editar la línea,
    dejando `foreign_price` inflado (≈ price_unit × 777 en vez de × 0,00129).

    La línea debe recibir también `foreign_inverse_rate` (la tasa inversa que la
    orden ya guarda, en la misma unidad que `init_conversion_rate`) sin alterar
    `foreign_currency_rate`, que sigue siendo Bs/USD.

    Alcance: estas pruebas cubren solo la serialización servidor -> PoS
    (`pos.order.line._export_for_ui`). La compañía de prueba usa `generic_coa`
    (base USD) y las tasas de la orden se inyectan con la semántica de una base
    Bs. La corrección de `get_rate()` / `set_unit_price` es JS y `l10n_ve_pos` no
    tiene infraestructura de pruebas JS; se valida con la reproducción manual
    documentada en el ticket.
    """

    FOREIGN_RATE = 777.42
    INVERSE_RATE = 0.001286312439374

    @classmethod
    def setup_company_data(cls, company_name, chart_template=None, **kwargs):
        # Mismo workaround que test_account_move_button_draft: l10n_ve_stock
        # restringe a un impuesto por producto y product_b del setup común
        # lleva dos.
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
        cls.product_a = cls.create_product("Producto Test", cls.categ_basic, 100.0)
        cls.adjust_inventory([cls.product_a], [10])

    def _create_order(self, inverse_rate=None):
        inverse_rate = self.INVERSE_RATE if inverse_rate is None else inverse_rate
        self.open_new_session()
        order_data = self.create_ui_order_data(
            [(self.product_a, 1)],
            customer=self.customer,
            is_invoiced=True,
            payments=[(self.cash_pm1, 100.0)],
        )
        data = order_data["data"]
        for command in data["statement_ids"]:
            command[2]["foreign_amount"] = round(command[2]["amount"] * inverse_rate, 2)
            command[2]["foreign_rate"] = inverse_rate
        data["foreign_amount_total"] = round(100.0 * inverse_rate, 2)
        data["foreign_currency_rate"] = self.FOREIGN_RATE
        data["foreign_inverse_rate"] = inverse_rate
        self.env["pos.order"].create_from_ui([order_data])
        return self.pos_session.order_ids

    def test_line_export_sends_inverse_rate_and_keeps_direct_rate(self):
        order = self._create_order()
        line = order.lines[:1]
        self.assertTrue(line)

        exported = line._export_for_ui(line)

        self.assertAlmostEqual(
            exported["foreign_inverse_rate"],
            self.INVERSE_RATE,
            places=12,
            msg="La línea debe recibir la tasa inversa guardada en la orden.",
        )
        self.assertAlmostEqual(
            exported["foreign_currency_rate"],
            self.FOREIGN_RATE,
            places=2,
            msg="foreign_currency_rate debe seguir siendo la tasa Bs/USD.",
        )

    def test_line_export_with_zero_inverse_rate_does_not_break(self):
        """Órdenes antiguas sin tasa inversa: la clave debe viajar igualmente (0)
        para que el PoS caiga a la tasa del día y no a la tasa Bs/USD."""
        order = self._create_order(inverse_rate=0.0)
        line = order.lines[:1]
        self.assertTrue(line)

        exported = line._export_for_ui(line)

        self.assertIn("foreign_inverse_rate", exported)
        self.assertFalse(exported["foreign_inverse_rate"])
