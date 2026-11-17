from lxml import etree

from odoo.tests import TransactionCase, tagged

AMOUNT_COLUMNS = [
    "amount_untaxed_signed",
    "amount_tax_signed",
    "amount_total_signed",
    "foreign_untaxed_total",
    "foreign_total_billed",
]


@tagged("post_install", "-at_install", "l10n_ve_accountant_invoice_list_columns")
class TestInvoiceListColumns(TransactionCase):
    """Las listas de facturas y notas (clientes y proveedores) agrupan los
    montos en Bs. y luego los de divisa, todos totalizan y tienen ancho fijo."""

    VIEWS = [
        "account.view_out_invoice_tree",
        "account.view_out_credit_note_tree",
        "account.view_in_invoice_bill_tree",
        "account.view_in_invoice_refund_tree",
    ]

    def _list_fields(self, xmlid):
        view = self.env.ref(xmlid)
        arch = self.env["account.move"].get_view(view.id, "list")["arch"]
        root = etree.fromstring(arch)
        return {f.get("name"): f for f in root.iter("field")}, [
            f.get("name") for f in root.iter("field")
        ]

    def test_amount_columns_order_bs_then_foreign(self):
        for xmlid in self.VIEWS:
            with self.subTest(view=xmlid):
                _fields, order = self._list_fields(xmlid)
                positions = [order.index(name) for name in AMOUNT_COLUMNS]
                self.assertEqual(positions, sorted(positions))
                self.assertEqual(
                    positions[-1] - positions[0],
                    len(AMOUNT_COLUMNS) - 1,
                    "Las cinco columnas de montos deben ser contiguas",
                )

    def test_amount_columns_have_sum_and_width(self):
        for xmlid in self.VIEWS:
            with self.subTest(view=xmlid):
                fields_by_name, _order = self._list_fields(xmlid)
                for name in AMOUNT_COLUMNS:
                    self.assertTrue(
                        fields_by_name[name].get("sum"),
                        f"{name} debe totalizar al pie de la lista",
                    )
                    self.assertTrue(
                        fields_by_name[name].get("width"),
                        f"{name} debe tener ancho predeterminado",
                    )

    def test_partner_column_has_width_and_name_is_native(self):
        for xmlid in self.VIEWS:
            with self.subTest(view=xmlid):
                view = self.env.ref(xmlid)
                arch = self.env["account.move"].get_view(view.id, "list")["arch"]
                root = etree.fromstring(arch)
                partner_cols = [
                    f for f in root.iter("field")
                    if f.get("name") == "invoice_partner_display_name"
                ]
                self.assertTrue(partner_cols)
                for col in partner_cols:
                    self.assertEqual(col.get("width"), "330px")
                name_col = next(f for f in root.iter("field") if f.get("name") == "name")
                self.assertFalse(name_col.get("width"), "Número conserva el ancho nativo")
