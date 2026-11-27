"""El gerente de ventas elimina cotizaciones con el permiso nativo (tarea 87425).

l10n_ve_sale ya no redefine sale.access_sale_order_manager. El gerente borra
borradores y órdenes canceladas, Odoo sigue impidiendo borrar órdenes enviadas
o confirmadas, y el vendedor no tiene permiso de borrado.
"""

import importlib.util

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user
from odoo.tools.misc import file_path

MIGRATION = "l10n_ve_sale/migrations/19.0.1.0.12/post-restore_sale_manager_unlink.py"


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestSaleOrderUnlinkManager(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.ves = cls.env.ref("base.VEF")
        cls.usd = cls.env.ref("base.USD")
        cls.company.write({
            "currency_id": cls.ves.id,
            "foreign_currency_id": cls.usd.id,
        })
        cls._set_rate(cls.usd, fields.Date.today(), 50.0)

        cls.partner = cls.env["res.partner"].create({"name": "Cliente borrado"})
        cls.product = cls.env["product.product"].create({
            "name": "Producto borrado",
            "list_price": 100.0,
        })
        cls.pricelist = cls.env["product.pricelist"].create({
            "name": "PL borrado VES",
            "currency_id": cls.ves.id,
            "company_id": cls.company.id,
        })
        cls.tax = cls.env["account.tax"].create({
            "name": "IVA 16% borrado",
            "amount": 16.0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": cls.company.id,
            "tax_group_id": cls.env["account.tax.group"].search([], limit=1).id,
        })

        # Logins con forma de email: new_test_user genera el mismo email para
        # logins que empiezan igual y l10n_ve_contact rechaza los duplicados.
        cls.manager = new_test_user(
            cls.env, login="ve_sale_manager@example.com",
            groups="sales_team.group_sale_manager",
        )
        cls.salesman = new_test_user(
            cls.env, login="ve_sale_salesman@example.com",
            groups="sales_team.group_sale_salesman_all_leads",
        )

    @classmethod
    def _set_rate(cls, currency, date, ves_per_unit):
        rate = cls.env["res.currency.rate"].search([
            ("currency_id", "=", currency.id),
            ("company_id", "=", cls.company.id),
            ("name", "=", date),
        ], limit=1)
        if rate:
            rate.inverse_company_rate = ves_per_unit
            return rate
        return cls.env["res.currency.rate"].create({
            "currency_id": currency.id,
            "company_id": cls.company.id,
            "name": date,
            "inverse_company_rate": ves_per_unit,
        })

    def _draft_order(self):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": self.pricelist.id,
            "company_id": self.company.id,
            "date_order": fields.Datetime.now(),
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 2,
                "price_unit": 1000.0,
                "tax_ids": [Command.set(self.tax.ids)],
            })],
        })

    def test_acl_values(self):
        """El gerente tiene borrado nativo sobre sale.order y sigue sin borrado
        sobre pickings."""
        self.assertTrue(self.env.ref("sale.access_sale_order_manager").perm_unlink)
        self.assertFalse(
            self.env.ref("sale_stock.access_stock_picking_sales").perm_unlink
        )

    def test_manager_unlinks_draft_with_lines(self):
        """El gerente borra un borrador con líneas y las líneas se van con la
        orden."""
        order = self._draft_order()
        lines = order.order_line
        self.assertTrue(lines)
        order.with_user(self.manager).unlink()
        self.assertFalse(order.exists())
        self.assertFalse(lines.exists())

    def test_manager_unlinks_cancelled(self):
        """El gerente borra una orden cancelada."""
        order = self._draft_order()
        order.action_cancel()
        self.assertEqual(order.state, "cancel")
        order.with_user(self.manager).unlink()
        self.assertFalse(order.exists())

    def test_manager_cannot_unlink_sent(self):
        """Odoo impide borrar una cotización enviada."""
        order = self._draft_order()
        order.write({"state": "sent"})
        with self.assertRaises(UserError):
            order.with_user(self.manager).unlink()
        self.assertTrue(order.exists())

    def test_manager_cannot_unlink_confirmed(self):
        """Odoo impide borrar una orden confirmada."""
        order = self._draft_order()
        order.action_confirm()
        self.assertEqual(order.state, "sale")
        with self.assertRaises(UserError):
            order.with_user(self.manager).unlink()
        self.assertTrue(order.exists())

    def test_salesman_cannot_unlink(self):
        """El vendedor, aun con acceso a todos los documentos, no puede
        borrar."""
        order = self._draft_order()
        with self.assertRaises(AccessError):
            order.with_user(self.salesman).unlink()
        self.assertTrue(order.exists())

    def test_migration_restores_manager_unlink(self):
        """La migración 19.0.1.0.12 devuelve el permiso de borrado que el
        override anterior dejaba en 0."""
        acl = self.env.ref("sale.access_sale_order_manager")
        acl.perm_unlink = False
        self.assertFalse(acl.perm_unlink)

        # La carpeta de la versión tiene puntos: no se importa como paquete.
        spec = importlib.util.spec_from_file_location(
            "l10n_ve_sale_post_restore_sale_manager_unlink", file_path(MIGRATION)
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migration.migrate(self.env.cr, "19.0.1.0.11")

        acl.invalidate_recordset()
        self.assertTrue(acl.perm_unlink)
