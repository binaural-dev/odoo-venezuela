from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged("l10n_ve_exchange_difference", "-at_install", "post_install")
class TestExchangeNoteProductDomain(TransactionCase):
    """Cubre el `domain` de `res.company.l10n_ve_exchange_note_product_id`
    (`models/res_company.py`): solo debe listar productos de tipo Servicio
    con el impuesto exento de venta (`exent_aliquot_sale`) Y el de compra
    (`exent_aliquot_purchase`) de la compañía asignados.

    No reutiliza el fixture pesado de `TestExchangeNoteReversal`
    (diarios, listas de precio, secuencias de ND) porque este `domain` es
    puramente un filtro de UI sobre `product.product` -- no depende de
    nada de eso, solo de la compañía y sus dos impuestos exentos.

    El `domain` del campo está declarado como STRING (no como lista):
    Odoo solo evalúa esa forma del lado del cliente web, nunca la aplica
    en el servidor al hacer `write`/`create` -- por eso estos tests no
    prueban un `ValidationError` (eso ya lo cubre
    `_check_l10n_ve_exchange_note_product_id` en
    `test_exchange_note_reversal.py`), sino que emulan la misma
    sustitución de variables que hace el cliente (los nombres de campo
    del `domain` se resuelven contra el propio record) y verifican que el
    domain resultante, aplicado con `search()`, deja pasar únicamente lo
    esperado."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company

        self.sale_exempt = self.env["account.tax"].create({
            "name": "Exento Venta (Test Domain)",
            "amount": 0,
            "type_tax_use": "sale",
        })
        self.purchase_exempt = self.env["account.tax"].create({
            "name": "Exento Compra (Test Domain)",
            "amount": 0,
            "type_tax_use": "purchase",
        })
        self.other_sale_tax = self.env["account.tax"].create({
            "name": "Otro Venta (Test Domain)",
            "amount": 16,
            "type_tax_use": "sale",
        })
        self.other_purchase_tax = self.env["account.tax"].create({
            "name": "Otro Compra (Test Domain)",
            "amount": 16,
            "type_tax_use": "purchase",
        })
        self.company.write({
            "exent_aliquot_sale": self.sale_exempt.id,
            "exent_aliquot_purchase": self.purchase_exempt.id,
        })

        # Cumple TODO (servicio + ambos impuestos exentos) -- debe aparecer.
        self.product_ok = self.env["product.product"].create({
            "name": "Producto OK (Test Domain)",
            "type": "service",
            "taxes_id": [(6, 0, [self.sale_exempt.id])],
            "supplier_taxes_id": [(6, 0, [self.purchase_exempt.id])],
        })
        # Tipo incorrecto (no es servicio) -- no debe aparecer.
        self.product_wrong_type = self.env["product.product"].create({
            "name": "Producto Tipo Incorrecto (Test Domain)",
            "type": "consu",
            "taxes_id": [(6, 0, [self.sale_exempt.id])],
            "supplier_taxes_id": [(6, 0, [self.purchase_exempt.id])],
        })
        # Impuesto de venta que no es el exento configurado -- no debe aparecer.
        self.product_wrong_sale_tax = self.env["product.product"].create({
            "name": "Producto Impuesto Venta Incorrecto (Test Domain)",
            "type": "service",
            "taxes_id": [(6, 0, [self.other_sale_tax.id])],
            "supplier_taxes_id": [(6, 0, [self.purchase_exempt.id])],
        })
        # Impuesto de compra que no es el exento configurado -- no debe aparecer.
        self.product_wrong_purchase_tax = self.env["product.product"].create({
            "name": "Producto Impuesto Compra Incorrecto (Test Domain)",
            "type": "service",
            "taxes_id": [(6, 0, [self.sale_exempt.id])],
            "supplier_taxes_id": [(6, 0, [self.other_purchase_tax.id])],
        })
        # Sin ningún impuesto asignado -- no debe aparecer.
        self.product_no_taxes = self.env["product.product"].create({
            "name": "Producto Sin Impuestos (Test Domain)",
            "type": "service",
        })

    def _eval_client_domain(self, record):
        """Emula la evaluación del `domain` string tal como lo hace el
        cliente web: sustituye `exent_aliquot_sale`/`exent_aliquot_purchase`
        por el valor de esos campos en `record` (mismo mecanismo con el
        que se evalúan los `domain` de campos Many2one que referencian
        otros campos del propio modelo, p.ej. `state_id`/`country_id` en
        `res.partner`)."""
        field = self.env["res.company"]._fields["l10n_ve_exchange_note_product_id"]
        domain_str = field.domain
        self.assertIsInstance(domain_str, str, "El domain debe seguir siendo un string evaluable por el cliente")
        local_vars = {
            "exent_aliquot_sale": record.exent_aliquot_sale.id,
            "exent_aliquot_purchase": record.exent_aliquot_purchase.id,
        }
        return safe_eval(domain_str, local_vars)

    def test_domain_string_shape(self):
        field = self.env["res.company"]._fields["l10n_ve_exchange_note_product_id"]
        self.assertIn("'type', '=', 'service'", field.domain)
        self.assertIn("taxes_id", field.domain)
        self.assertIn("supplier_taxes_id", field.domain)

    def test_config_settings_domain_matches_company(self):
        """El selector real que ve el usuario es
        `res.config.settings.l10n_ve_exchange_note_product_id`, un
        `related='company_id...'` -- Odoo NO propaga un domain string de
        un related a menos que el propio campo lo declare explícito
        (`_related_domain`, `odoo/orm/fields_relational.py`: descarta
        cualquier domain de tipo string salvo que el campo sea
        `inherited`). Si este test fallara, el selector de Ajustes
        quedaría sin ningún filtro (regresión detectada en la revisión
        de este PR)."""
        company_field = self.env["res.company"]._fields["l10n_ve_exchange_note_product_id"]
        settings_field = self.env["res.config.settings"]._fields["l10n_ve_exchange_note_product_id"]
        self.assertIsInstance(settings_field.domain, str, "El related debe declarar su propio domain string")
        self.assertEqual(settings_field.domain, company_field.domain)

    def test_domain_filters_correctly_when_taxes_configured(self):
        domain = self._eval_client_domain(self.company)
        expected = [
            ("type", "=", "service"),
            ("taxes_id", "in", [self.sale_exempt.id]),
            ("supplier_taxes_id", "in", [self.purchase_exempt.id]),
        ]
        self.assertEqual(domain, expected)

        candidates = (
            self.product_ok
            | self.product_wrong_type
            | self.product_wrong_sale_tax
            | self.product_wrong_purchase_tax
            | self.product_no_taxes
        )
        found = self.env["product.product"].search(domain + [("id", "in", candidates.ids)])
        self.assertEqual(found, self.product_ok, "Solo el producto que cumple TODAS las condiciones debe pasar el filtro")

    def test_domain_shows_nothing_when_purchase_tax_not_configured(self):
        self.company.write({"exent_aliquot_purchase": False})
        domain = self._eval_client_domain(self.company)
        self.assertIn(("supplier_taxes_id", "in", [False]), domain)

        found = self.env["product.product"].search(
            domain + [("id", "in", [self.product_ok.id, self.product_wrong_type.id])]
        )
        self.assertFalse(found, "Sin impuesto de compra exento configurado, el filtro no debe mostrar ningún producto")

    def test_domain_shows_nothing_when_sale_tax_not_configured(self):
        self.company.write({"exent_aliquot_sale": False})
        domain = self._eval_client_domain(self.company)
        self.assertIn(("taxes_id", "in", [False]), domain)

        found = self.env["product.product"].search(
            domain + [("id", "in", [self.product_ok.id, self.product_wrong_type.id])]
        )
        self.assertFalse(found, "Sin impuesto de venta exento configurado, el filtro no debe mostrar ningún producto")
