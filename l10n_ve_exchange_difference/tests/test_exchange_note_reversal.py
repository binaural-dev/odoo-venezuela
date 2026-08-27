from unittest.mock import patch
import inspect

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged("l10n_ve_exchange_difference", "-at_install", "post_install")
class TestExchangeNoteReversal(TransactionCase):
    """Prueba el flujo REAL tal como lo haría un usuario en el navegador:
    factura en USD -> botón 'Registrar Pago' (wizard `account.payment.register`,
    vía `Form`) -> pago en USD en una fecha con tasa distinta -> Odoo concilia
    internamente (llamando a nuestro `account.move.line.reconcile()`
    sobreescrito). Confirma, en un TransactionCase real (no `odoo shell`
    crudo), que el residual de diferencial cambiario se liquida con una
    ND/NC real sin el `RecursionError` que sí aparecía al intentar usar
    `account.move.reversal` para la Nota de Crédito."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.usd = cls.env.ref("base.USD")
        cls.usd.active = True

        # `expected_currency_rate`/`_get_conversion_rate` (lo que Odoo usa
        # para valorar la factura al contabilizarla) dependen de que la
        # compañía tenga su propia moneda (VEF) Y la "moneda alterna"
        # (`foreign_currency_id`, campo de `l10n_ve_rate`) configuradas --
        # sin esto, en una base limpia sin datos de módulo la compañía
        # queda con su moneda por defecto (USD) y sin moneda alterna, y el
        # cálculo de tasa cae al 1.0 por defecto sin importar qué
        # `res.currency.rate` se inyecten. Mismo patrón que usa
        # `l10n_ve_igtf` en sus tests (`IGTFTestCommon.setUp`,
        # `l10n_ve_igtf/tests/test_igtf_common_providers_formal_VEF.py`).
        # `country_id` también explícito -- en al menos una base real
        # `base.main_company` quedó sin país configurado, y los
        # `account.tax` creados más abajo con `country_id` derivado de
        # `cls.company.country_id` (vacío en ese caso) reventaban el
        # `NOT NULL` de `account_tax.country_id` en Postgres.
        cls.company.write({
            "currency_id": cls.env.ref("base.VEF").id,
            "foreign_currency_id": cls.usd.id,
            "country_id": cls.company.country_id.id or cls.env.ref("base.ve").id,
        })

        # Dos tasas distintas para forzar un diferencial cambiario real al
        # conciliar la factura (fecha 2026-01-01, tasa MAYOR) contra el pago
        # (2026-08-01, tasa MENOR) -- el pago vale MENOS en VEF de lo que la
        # factura necesitaba, dejando un residual en DÉBITO ("falta") del
        # lado de la propia factura -> Nota de Crédito.
        #
        # `company_rate` va INVERTIDO (1/tasa_vef_por_usd) -- mismo patrón
        # que usa `l10n_ve_igtf` en sus tests
        # (`l10n_ve_igtf/tests/test_igtf_common_providers_formal_VEF.py`):
        # ahí `self.rate = 390.2944` (VEF por USD) pero se escribe
        # `'company_rate': 1/self.rate`. Pasarlo directo (sin invertir, como
        # se hacía antes) produce tasas de escala absurda (~0.025 en vez de
        # ~40) y diferenciales cambiarios minúsculos/irreales. También hay
        # que activar la moneda en el MISMO `write()` que las tasas.
        cls.rate_invoice_date = 40.0
        cls.rate_payment_date = 36.0
        cls.usd.write({
            "active": True,
            "rate_ids": [
                Command.create({
                    "name": "2026-01-01",
                    "company_rate": 1 / cls.rate_invoice_date,
                }),
                Command.create({
                    "name": "2026-08-01",
                    "company_rate": 1 / cls.rate_payment_date,
                }),
            ],
        })

        cls.partner = cls.env["res.partner"].create({"name": "Cliente Prueba Reversal"})
        cls.partner.property_product_pricelist = False

        # Cuentas base con FALLBACK de creación -- no basta con
        # `search()` solo: en al menos un entorno real la compañía no
        # tenía chart of accounts instalado en absoluto, y una búsqueda
        # sin fallback dejaba `property_account_receivable_id` vacío --
        # Odoo rechaza cualquier factura para ese partner con
        # `RedirectWarning` ("Cannot find a chart of accounts"). Mismo
        # patrón robusto que usa `l10n_ve_igtf`
        # (`get_or_create_account`, `IGTFTestCommon.setUp`), pero con
        # códigos PROPIOS (sufijo "REV") -- no se reutiliza ese mismo
        # helper ni sus mismos códigos: en una base compartida entre
        # varios archivos de test, `get_or_create_account` busca por
        # `code` SIN filtrar por compañía, así que copiar sus códigos
        # tal cual arriesgaba encontrar/reescribir la cuenta de OTRO
        # fixture en vez de crear una propia.
        cls.acc_receivable = cls.env["account.account"].search(
            [*cls.env["account.account"]._check_company_domain(cls.company), ("account_type", "=", "asset_receivable")],
            limit=1,
        )
        if not cls.acc_receivable:
            cls.acc_receivable = cls.env["account.account"].create({
                "name": "Cuentas por Cobrar Prueba Reversal",
                "code": "1101REV",
                "account_type": "asset_receivable",
                "reconcile": True,
                "company_ids": [Command.set([cls.company.id])],
            })
        cls.partner.property_account_receivable_id = cls.acc_receivable.id

        cls.acc_payable = cls.env["account.account"].search(
            [*cls.env["account.account"]._check_company_domain(cls.company), ("account_type", "=", "liability_payable")],
            limit=1,
        )
        if not cls.acc_payable:
            cls.acc_payable = cls.env["account.account"].create({
                "name": "Cuentas por Pagar Prueba Reversal",
                "code": "2101REV",
                "account_type": "liability_payable",
                "reconcile": True,
                "company_ids": [Command.set([cls.company.id])],
            })
        cls.partner.property_account_payable_id = cls.acc_payable.id

        # Cuentas de ganancia/pérdida cambiaria -- `company.income_currency_exchange_account_id`/
        # `expense_currency_exchange_account_id` (campos nativos de
        # Odoo) NO se asumen preconfiguradas por el chart of accounts
        # de la base: en al menos un entorno real quedaron vacías,
        # dejando la línea de la ND/NC sin `account_id` y reventando el
        # `CHECK account_move_line_check_accountable_required_fields`
        # de Postgres al crearla.
        cls.acc_exchange_gain = cls.env["account.account"].create({
            "name": "Ganancia Cambiaria Prueba Reversal",
            "code": "76001REV",
            "account_type": "income_other",
            "company_ids": [Command.set([cls.company.id])],
        })
        cls.acc_exchange_loss = cls.env["account.account"].create({
            "name": "Pérdida Cambiaria Prueba Reversal",
            "code": "66001REV",
            "account_type": "expense",
            "company_ids": [Command.set([cls.company.id])],
        })
        # `company.currency_exchange_journal_id` -- campo NATIVO de Odoo
        # (diario "Ganancia o Pérdida en Cambio", Ajustes > Contabilidad),
        # exigido por el propio núcleo (`_create_exchange_difference_moves`,
        # `account/models/account_move_line.py`) ANTES de que este módulo
        # intercepte la creación de la ND/NC: sin él configurado, Odoo
        # revienta con `UserError` incluso cuando `l10n_ve_exchange_use_nd_nc`
        # ya está activo. Distinto de `income_currency_exchange_account_id`/
        # `expense_currency_exchange_account_id` (las CUENTAS) -- este es el
        # DIARIO donde Odoo registraría su asiento genérico si este módulo
        # no lo redirigiera.
        cls.exchange_journal = cls.env["account.journal"].create({
            "name": "Diferencial Cambiario Prueba Reversal",
            "type": "general",
            "code": "EXCHREV",
            "company_id": cls.company.id,
        })
        cls.company.write({
            "income_currency_exchange_account_id": cls.acc_exchange_gain.id,
            "currency_exchange_journal_id": cls.exchange_journal.id,
            "expense_currency_exchange_account_id": cls.acc_exchange_loss.id,
        })

        # `company.exent_aliquot_sale` depende de configuración que no
        # existe en una base limpia sin datos de módulo -- se CREAN los
        # impuestos al 0% explícitamente en vez de buscar uno ya existente
        # (ej. "0% Exports"): un `search()` depende de qué datos demo se
        # cargaron, y eso varía según el módulo/orden de instalación --
        # corriendo con `--without-demo=True` (subárbol aislado) no existe
        # ningún impuesto demo y la búsqueda siempre da vacío, mientras que
        # junto a otros módulos con demo puede o no encontrar uno. Mismo
        # bug encontrado y corregido en `l10n_ve_igtf`
        # (`test_igtf_common_partner_formal_VEF.py`, `purchase_exent`).
        cls.exent_tax_group = cls.env['account.tax.group'].create({
            'name': 'IVA Test Reversal',
            'country_id': cls.company.country_id.id,
        })
        cls.exent = cls.env['account.tax'].create({
            'name': 'IVA exento (Test Reversal)',
            'amount': 0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'company_id': cls.company.id,
            'tax_group_id': cls.exent_tax_group.id,
            'country_id': cls.company.country_id.id,
        })
        # `supplier_taxes_id` explícito -- sin esto, el default que arma
        # Odoo para ese campo en `create()` puede traer más de un impuesto
        # en bases con varios impuestos de compra al 0% configurados, y
        # `l10n_ve_accountant` (`_enforce_single_tax_vals`) rechaza
        # cualquier producto con más de un impuesto de compra asignado.
        cls.exent_purchase = cls.env['account.tax'].create({
            'name': 'Compra exenta (Test Reversal)',
            'amount': 0,
            'amount_type': 'percent',
            'type_tax_use': 'purchase',
            'company_id': cls.company.id,
            'tax_group_id': cls.exent_tax_group.id,
            'country_id': cls.company.country_id.id,
        })
        # `l10n_ve_exchange_note_product_id` exige (`_check_l10n_ve_exchange_note_product_id`,
        # `models/res_company.py`) que el producto sea un servicio, que su
        # cuenta de ingreso sea una de las cuentas nativas de
        # ganancia/pérdida por diferencial cambiario de la compañía, y que
        # su impuesto de venta sea el mismo exento por defecto
        # (`company.exent_aliquot_sale`) -- se deja explícito acá para que
        # el producto de prueba cumpla ese dominio sin depender de datos
        # de una base con módulos ya instalados.
        cls.company.exent_aliquot_sale = cls.exent.id
        cls.note_product = cls.env["product.product"].create({
            "name": "Diferencial Test Reversal",
            "type": "service",
            "taxes_id": [(6, 0, cls.exent.ids)],
            "supplier_taxes_id": [(6, 0, cls.exent_purchase.ids)],
            "property_account_income_id": cls.company.income_currency_exchange_account_id.id,
            "property_account_expense_id": cls.company.expense_currency_exchange_account_id.id,
        })
        cls.company.l10n_ve_exchange_note_product_id = cls.note_product.id

        # `account_invoice_pricelist` exige un `pricelist_id` en la MISMA
        # moneda del documento en toda factura/nota -- las ND/NC de
        # diferencial siempre se crean en moneda de compañía (VEF), así
        # que la lista configurada debe estar en esa moneda también (ver
        # `_check_l10n_ve_exchange_note_pricelist_id`, `models/res_company.py`).
        cls.note_pricelist = cls.env["product.pricelist"].create({
            "name": "Diferencial Test Reversal (VEF)",
            "currency_id": cls.company.currency_id.id,
        })
        cls.company.l10n_ve_exchange_note_pricelist_id = cls.note_pricelist.id

        # Diario dedicado de ND, con su secuencia propia asignada -- desde
        # este fix, `_create_exchange_difference_note` exige AMBOS
        # (diario `type='sale'`/`is_debit=True` Y su secuencia
        # configurada) antes de emitir cualquier ND: sin esto, una ND
        # terminaría numerada con la secuencia de FACTURAS del diario de
        # venta (bug real corregido, ver `models/account_journal_views.xml`
        # y `_create_exchange_difference_note`).
        cls.debit_note_sequence = cls.env["ir.sequence"].create({
            "name": "ND Diferencial Cambiario Test",
            "code": "l10n.ve.exchange.debit.note.test",
            "company_id": cls.company.id,
            "prefix": "NDDIFT/%(year)s/",
            "padding": 4,
        })
        cls.debit_note_journal = cls.env["account.journal"].create({
            "name": "ND Diferencial Cambiario Test",
            "type": "sale",
            "code": "NDDIFT",
            "company_id": cls.company.id,
            "is_debit": True,
            "l10n_ve_exchange_debit_note_sequence_id": cls.debit_note_sequence.id,
            # `refund_sequence: True` -- revertir una ND ya NO
            # autoprovisiona `refund_sequence_id` en silencio sobre este
            # diario (ese diario `is_debit=True` no es exclusivo del
            # módulo, es infraestructura fiscal real): ahora exige que
            # esté configurado de antemano, igual que la NC directa
            # exige `refund_sequence_id` en el diario de venta.
            "refund_sequence": True,
        })
        cls.company.l10n_ve_exchange_use_nd_nc = True

        # Diario de venta EXPLÍCITO -- NO se busca "cualquier diario
        # `type='sale'`" (bug real confirmado: esa búsqueda, sin excluir
        # `is_debit`, podía encontrar el propio `debit_note_journal`
        # recién creado arriba -- también `type='sale'` -- y usarlo como
        # diario de facturas NORMALES, numerándolas con la secuencia
        # dedicada de ND y produciendo `UniqueViolation` en
        # `account_move_unique_name` al chocar dos facturas distintas
        # numeradas ambas "NDDIFT/2026/0001").
        # `refund_sequence: True` -- desde el fix de B5 (revisión de
        # código), `_create_exchange_difference_note` YA NO autoprovisiona
        # `refund_sequence_id` en silencio sobre el diario de venta al
        # emitir una NC (rama de pérdida cambiaria): ahora exige que esté
        # configurado de antemano, igual que exige la secuencia dedicada
        # de ND. `od_journal_sequence.account_journal.create()` la
        # autogenera acá mismo cuando el diario nace con
        # `refund_sequence=True` (`type='sale'`).
        cls.sale_journal = cls.env["account.journal"].create({
            "name": "Ventas Prueba Reversal",
            "type": "sale",
            "code": "VREV",
            "company_id": cls.company.id,
            "refund_sequence": True,
        })

        # Diario de compras, con fallback de creación -- necesario para
        # el caso de factura de PROVEEDOR
        # (`test_fallback_tags_generic_exchange_move_for_vendor_bill`):
        # sin diario de compras, el `Form` de una factura `in_invoice`
        # revienta con `UserError: No journal could be found ... for
        # any of those types: purchase` antes de llegar siquiera a la
        # lógica de este módulo.
        cls.purchase_journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.purchase_journal:
            cls.purchase_journal = cls.env["account.journal"].create({
                "name": "Compras Prueba Reversal",
                "type": "purchase",
                "code": "CREV",
                "company_id": cls.company.id,
            })

        # Se reusa un diario de banco en USD si ya existe uno bien
        # configurado (con métodos de pago/cuentas asignadas); si no (base
        # limpia sin datos de módulo), se crea uno mínimo -- Odoo arma la
        # cuenta contable y los métodos de pago del diario automáticamente
        # al crear un `account.journal` de tipo `bank`.
        cls.usd_bank_journal = cls.env["account.journal"].search(
            [
                *cls.env["account.journal"]._check_company_domain(cls.company),
                ("type", "=", "bank"), ("currency_id", "=", cls.usd.id),
            ],
            limit=1,
        )
        if not cls.usd_bank_journal:
            bank_account = cls.env["account.account"].create({
                "name": "Banco USD Prueba Reversal",
                "code": "BUSDR01",
                "account_type": "asset_cash",
                "currency_id": cls.usd.id,
            })
            cls.usd_bank_journal = cls.env["account.journal"].create({
                "name": "Banco USD Prueba Reversal",
                "type": "bank",
                "code": "BUSDR",
                "currency_id": cls.usd.id,
                "company_id": cls.company.id,
                "default_account_id": bank_account.id,
                # El asistente "Registrar Pago" exige un método de pago
                # (`payment_method_line_id`) -- se deja uno solo (manual),
                # con cuenta asignada (si no, Odoo rechaza el método).
                "inbound_payment_method_line_ids": [(5, 0, 0), (0, 0, {
                    "name": "Manual",
                    "payment_method_id": cls.env.ref("account.account_payment_method_manual_in").id,
                    "payment_account_id": bank_account.id,
                })],
                # Método saliente también, para poder pagar facturas de
                # PROVEEDOR (caso de fallback: factura que no es de
                # cliente, ver `test_fallback_tags_generic_exchange_move_for_vendor_bill`).
                "outbound_payment_method_line_ids": [(5, 0, 0), (0, 0, {
                    "name": "Manual",
                    "payment_method_id": cls.env.ref("account.account_payment_method_manual_out").id,
                    "payment_account_id": bank_account.id,
                })],
            })
        # Cuentas de ingreso/gasto propias -- NO las de ganancia/pérdida
        # cambiaria (`acc_exchange_gain`/`acc_exchange_loss`, ésas son
        # EXCLUSIVAS del producto de la nota, `_check_l10n_ve_exchange_note_product_id`
        # las exige distintas de cualquier otro uso). Sin cuenta propia
        # aquí y sin fiscal position por defecto en la compañía, CADA
        # factura creada con este producto (`_create_invoice`, usado por
        # casi todos los tests de este archivo) revienta con
        # `account_move_line_check_accountable_required_fields` al
        # agregar la línea.
        cls.acc_sale_income = cls.env["account.account"].create({
            "name": "Ingresos Prueba Reversal",
            "code": "4002REV2",
            "account_type": "income",
            "company_ids": [Command.set([cls.company.id])],
        })
        cls.acc_sale_expense = cls.env["account.account"].create({
            "name": "Gastos Prueba Reversal",
            "code": "5002REV2",
            "account_type": "expense",
            "company_ids": [Command.set([cls.company.id])],
        })
        cls.sale_product = cls.env["product.product"].create({
            "name": "Servicio Test Reversal",
            "type": "service",
            "taxes_id": [(6, 0, cls.exent.ids)],
            "supplier_taxes_id": [(6, 0, cls.exent_purchase.ids)],
            "property_account_income_id": cls.acc_sale_income.id,
            "property_account_expense_id": cls.acc_sale_expense.id,
        })

        # Diario de banco en la moneda DE COMPAÑÍA (VEF) -- necesario para
        # reproducir el caso "factura en USD pagada directo en VEF"
        # (`test_exchange_difference_settled_with_company_currency_payment`):
        # a diferencia de `usd_bank_journal`, aquí la línea de conciliación
        # del pago queda en VEF, distinta de la moneda de la factura.
        cls.vef_bank_journal = cls.env["account.journal"].search(
            [
                *cls.env["account.journal"]._check_company_domain(cls.company),
                ("type", "=", "bank"), ("currency_id", "=", False),
            ],
            limit=1,
        )
        if not cls.vef_bank_journal:
            vef_bank_account = cls.env["account.account"].create({
                "name": "Banco VEF Prueba Reversal",
                "code": "BVEFR01",
                "account_type": "asset_cash",
            })
            cls.vef_bank_journal = cls.env["account.journal"].create({
                "name": "Banco VEF Prueba Reversal",
                "type": "bank",
                "code": "BVEFR",
                "company_id": cls.company.id,
                "default_account_id": vef_bank_account.id,
                "inbound_payment_method_line_ids": [(5, 0, 0), (0, 0, {
                    "name": "Manual",
                    "payment_method_id": cls.env.ref("account.account_payment_method_manual_in").id,
                    "payment_account_id": vef_bank_account.id,
                })],
                # Método saliente también -- sin cuenta asignada,
                # `l10n_ve_accountant._check_payment_method_line_accounts`
                # rechaza el diario al crearlo. Mismo patrón que
                # `usd_bank_journal` arriba.
                "outbound_payment_method_line_ids": [(5, 0, 0), (0, 0, {
                    "name": "Manual",
                    "payment_method_id": cls.env.ref("account.account_payment_method_manual_out").id,
                    "payment_account_id": vef_bank_account.id,
                })],
            })

    def test_odoo_core_api_compatibility(self):
        """COMPATIBILITY GUARD: verifica que Odoo 19.x `_prepare_reconciliation_single_partial`
        tenga la firma y estructura exacta esperada. Este módulo sobrescribe un método
        INTERNO de Odoo (no público), acoplándose fuertemente a su implementación.

        Si esta prueba falla, es señal de que Odoo cambió internamente de forma
        incompatible, y el código que stashea `debit_values['aml']` y `credit_values['aml']`
        puede haber quedado obsoleto -- necesita revisión manual.

        Verificado contra: Odoo 19.0-20260710
        See: l10n_ve_exchange_difference/models/account_move_line.py:59-93
        """
        aml_model = self.env['account.move.line']

        # `getattr(aml_model, ...)` resolvería NUESTRO propio override
        # (definido en este mismo módulo, ver `account_move_line.py`),
        # no el método de CORE -- inspeccionar esa firma sería comparar
        # nuestra propia copia contra sí misma, siempre verde, sin
        # detectar jamás un cambio real de Odoo. Hay que recorrer el
        # MRO y tomar la función definida específicamente en el módulo
        # `account` de core, saltando la nuestra (y la de cualquier
        # otro addon instalado que también la sobrescriba).
        core_method = None
        for klass in type(aml_model).__mro__:
            if klass.__module__ == 'odoo.addons.account.models.account_move_line':
                core_method = klass.__dict__.get('_prepare_reconciliation_single_partial')
                if core_method is not None:
                    break
        self.assertIsNotNone(
            core_method,
            "Odoo core method _prepare_reconciliation_single_partial not found or was removed"
        )

        # Verificar parámetros exactos -- función SIN bind, `self` sí
        # aparece en la firma (a diferencia de `getattr` sobre una
        # instancia, que lo omite).
        sig = inspect.signature(core_method)
        expected_params = {'self', 'debit_values', 'credit_values', 'shadowed_aml_values'}
        actual_params = set(sig.parameters.keys())
        self.assertEqual(expected_params, actual_params,
            f"_prepare_reconciliation_single_partial signature changed. "
            f"Expected params: {expected_params}, got: {actual_params}. "
            f"l10n_ve_exchange_difference may be incompatible with this Odoo version."
        )

        # Verificar que shadowed_aml_values tenga default (es opcional)
        self.assertIsNot(sig.parameters['shadowed_aml_values'].default, inspect.Parameter.empty,
            "_prepare_reconciliation_single_partial shadowed_aml_values should have a default value"
        )

    def test_missing_aml_key_raises_user_error(self):
        """El guard de claves de `_prepare_reconciliation_single_partial`
        (`account_move_line.py`) -- el que el propio docstring del método
        llama "el único con valor real" frente al guard de firma de
        `test_odoo_core_api_compatibility`, que solo detecta un
        `TypeError` de Odoo, no un cambio silencioso de claves -- nunca
        tenía un test que lo ejercitara directamente. Se llama al método
        real con dicts que faltan la clave `'aml'` (simulando el
        escenario que el guard existe para atrapar: un futuro Odoo 19.x
        que cambie esa clave sin cambiar la firma) y se confirma que
        aborta con `UserError` (no `RuntimeError` -- ese sale como
        "Internal Server Error" genérico en vez de mostrar el mensaje
        explicativo en un diálogo), no que mal-atribuya la nota en
        silencio."""
        aml_model = self.env['account.move.line']
        with self.assertRaises(UserError):
            aml_model._prepare_reconciliation_single_partial(
                debit_values={'not_aml': object()},
                credit_values={'aml': object()},
            )
        with self.assertRaises(UserError):
            aml_model._prepare_reconciliation_single_partial(
                debit_values={'aml': object()},
                credit_values={'not_aml': object()},
            )

    def _create_invoice(self, invoice_date, journal=None):
        """Mismo patrón que usa `l10n_ve_igtf` para sus facturas de prueba
        (`IGTFTestCommon._create_invoice_usd`, ver
        `l10n_ve_igtf/tests/test_igtf_common_providers_formal_VEF.py`):
        el encabezado se guarda primero con un `Form`, y las líneas se
        agregan en un SEGUNDO `Form` sobre el registro ya guardado -- así
        se disparan los onchange/recompute de impuestos y totales en cada
        paso, en vez de dejar todo en un solo `create()` con
        `invoice_line_ids` embebido de una vez.

        `journal` opcional -- por defecto `self.sale_journal` (el de la
        mayoría de los tests, ya con `refund_sequence` configurada); un
        test que necesite reproducir el escenario de un diario SIN esa
        secuencia (ej. `test_regular_accountant_gets_user_error_...`) pasa
        el suyo propio."""
        with Form(self.env["account.move"].with_context(default_move_type="out_invoice")) as inv_form:
            inv_form.partner_id = self.partner
            inv_form.invoice_date = invoice_date
            # `journal_id` ANTES que `currency_id`: el onchange del diario
            # reasigna la moneda a la del propio diario (VEF, la de la
            # compañía) si se hace en el orden contrario, pisando el USD.
            inv_form.journal_id = journal or self.sale_journal
            inv_form.currency_id = self.usd
        invoice = inv_form.save()

        with Form(invoice) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.sale_product
                line.quantity = 1
                line.price_unit = 100.0
        return inv_form_edit.save()

    def test_exchange_difference_settled_by_real_note_via_register_payment(self):
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        # Botón "Registrar Pago" de la factura, simulado con Form (igual que
        # el navegador): mismo monto (100 USD) que la factura, pero pagado en
        # una fecha con una tasa distinta -- ahí nace el diferencial.
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        # La ND/NC se crea de forma síncrona dentro de la propia
        # transacción de conciliación (`_create_exchange_difference_moves`,
        # ver `account_move_line.py`) -- el `flush()` no es necesario para
        # que exista, pero se deja para invalidar la caché ORM antes de
        # leer los campos recién escritos.
        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(notes), 1, "Debió crearse exactamente una ND/NC de diferencial cambiario.")
        note = notes[0]
        self.assertEqual(note.state, "posted")
        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(note_line.amount_residual))

        # Rama pineada, no autoconsistente: con `rate_invoice_date` (40.0)
        # > `rate_payment_date` (36.0) del `setUpClass`, el residual queda
        # en DÉBITO ("falta") -> Nota de Crédito, siempre -- nunca ND.
        # Monto determinista: 100 USD × (40 - 36) = 400.0 Bs.
        self.assertEqual(note.l10n_ve_exchange_invoice_id, invoice)
        self.assertTrue(note.l10n_ve_exchange_is_credit_note)
        self.assertEqual(note.move_type, "out_refund")
        self.assertEqual(note.reversed_entry_id, invoice)
        self.assertEqual(note.amount_total, 400.0)
        self.assertEqual(note.invoice_line_ids.price_unit, 400.0)
        self.assertEqual(note.invoice_line_ids.account_id, self.company.expense_currency_exchange_account_id)
        self.assertEqual(note.date, fields.Date.from_string("2026-08-01"))
        self.assertEqual(
            note.pricelist_id, self.note_pricelist,
            "La nota debió usar la lista de precios configurada para diferencial cambiario.",
        )

    def test_exchange_difference_settled_with_company_currency_payment(self):
        """Mismo flujo que `test_exchange_difference_settled_by_real_note_via_register_payment`,
        pero pagando la factura en USD directo con un diario de banco en
        VEF (la moneda de compañía) -- reproduce el reporte del usuario
        ("pago una factura en dólares con VEF"). Antes de este fix,
        `reconcile()` exigía `invoice_line.currency_id == payment_line.currency_id`;
        al pagar en VEF una factura en USD esa igualdad nunca se cumplía,
        y el diferencial cambiario se perdía por completo (ni ND/NC propia
        ni asiento genérico de Odoo, por el `no_exchange_difference=True`).

        Este es también el Caso 4 del ticket ("Factura en $$ Pagada en Bs
        indexado") -- vía el wizard REAL `account.payment.register`, no
        `.reconcile()` crudo. "Indexado" no es un toggle que aplique acá:
        `indexed_default` (`l10n_ve_accountant/wizard/account_payment_register.py`)
        solo es EDITABLE en el wizard cuando `currency_id != company_currency_id`
        (`readonly="... or company_currency_id == currency_id"`,
        `l10n_ve_accountant/wizard/account_payment_register.xml:13`) -- para
        un pago en VEF (la moneda de compañía) ese campo queda readonly y
        `_get_conversion_date()` siempre usa `payment_date`, sea cual sea su
        valor. Ver `test_indexed_default_is_readonly_for_company_currency_payments`
        abajo, que deja esto explícito y a prueba de regresión."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.vef_bank_journal
            # El wizard, por defecto, mantiene la moneda de la factura (USD)
            # sin importar la moneda del diario -- para reproducir el
            # reporte real ("pago una factura en dólares con VEF") hay que
            # forzar explícitamente la moneda del PAGO a VEF, tal como haría
            # un usuario que cambia ese campo en el formulario.
            pay_form.currency_id = self.company.currency_id
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        self.assertEqual(payment_wizard.currency_id, self.company.currency_id)
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(
            len(notes), 1,
            "Debió crearse exactamente una ND/NC de diferencial cambiario aun pagando en VEF "
            "una factura en USD.",
        )
        note = notes[0]
        self.assertEqual(note.state, "posted")
        self.assertEqual(note.l10n_ve_exchange_invoice_id, invoice)
        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(note_line.amount_residual))

        # Mismas tasas del `setUpClass` (40.0 factura / 36.0 pago) que
        # `test_exchange_difference_settled_by_real_note_via_register_payment`
        # -- rama NC, mismo monto determinista: 100 USD × (40 - 36) = 400.0 Bs.
        self.assertEqual(note.move_type, "out_refund")
        self.assertEqual(note.reversed_entry_id, invoice)
        self.assertEqual(note.amount_total, 400.0)
        self.assertEqual(note.invoice_line_ids.price_unit, 400.0)
        self.assertEqual(note.invoice_line_ids.account_id, self.company.expense_currency_exchange_account_id)

    def test_indexed_default_is_readonly_for_company_currency_payments(self):
        """`indexed_default` -- el toggle 'indexado'/'no indexado' de
        `l10n_ve_accountant` -- solo es EDITABLE en el wizard cuando la
        moneda del PAGO es distinta de la moneda de compañía
        (`readonly="indexaxion_payment_mode != 'to_agreed' or
        company_currency_id == currency_id"`,
        `l10n_ve_accountant/wizard/account_payment_register.xml:13`). Al
        pagar una factura en USD directo con VEF (Caso 4 del ticket:
        "Factura en $$ Pagada en Bs"), ese campo queda readonly y
        `_get_conversion_date()` (`l10n_ve_accountant/wizard/account_payment_register.py`)
        siempre usa `payment_date`, sea cual sea su valor -- "indexado" no
        es un escenario distinto a pagar en VEF sin más, es el ÚNICO
        comportamiento posible. Documenta explícitamente por qué
        `test_exchange_difference_settled_with_company_currency_payment`
        (arriba) no necesita -- ni PUEDE -- variar `indexed_default` para
        cubrir ese caso del ticket."""
        self.company.indexaxion_payment_mode = "to_agreed"
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.vef_bank_journal
            pay_form.currency_id = self.company.currency_id
            pay_form.save()
            with self.assertRaises(
                AssertionError,
                msg="`indexed_default` debió quedar readonly al pagar en la "
                "moneda de la propia compañía (VEF).",
            ):
                pay_form.indexed_default = False

    def test_indexed_default_false_on_foreign_payment_produces_no_exchange_note(self):
        """Complemento de negocio de `test_indexed_default_is_readonly_for_company_currency_payments`:
        acá SÍ se puede editar `indexed_default` (pago en USD, moneda
        distinta de la de compañía) y se pone en `False` -- con eso,
        `_get_conversion_date()` (`l10n_ve_accountant/wizard/account_payment_register.py`)
        usa la fecha de la FACTURA (no la del pago) para valorar el pago
        en moneda de compañía, así que aunque la tasa cambió entre
        factura y pago, el pago queda contabilizado con la MISMA
        valorización que la factura -- residual en VEF cero, sin
        diferencial, sin ND/NC. Mismas fechas/tasas que
        `test_exchange_difference_credit_note_branch` (que SÍ genera una
        NC con `indexed_default` en su valor por defecto, `True`) para
        que quede claro que la única variable es el toggle."""
        self.company.indexaxion_payment_mode = "to_agreed"
        self.usd.write({
            "active": True,
            "rate_ids": [
                Command.create({
                    "name": "2038-01-01",
                    "company_rate": 1 / 40.0,
                }),
                Command.create({
                    "name": "2038-08-01",
                    "company_rate": 1 / 36.0,
                }),
            ],
        })

        invoice = self._create_invoice("2038-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2038-08-01"
            pay_form.indexed_default = False
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))
        payment.action_post()

        self.env.cr.flush()
        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        self.assertEqual(
            invoice.payment_state, "paid",
            "La factura debió quedar completamente pagada, sin residual "
            "pendiente, al usar la tasa de la FACTURA para valorar el pago.",
        )
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(
            self.company.currency_id.is_zero(inv_line.amount_residual),
            "Con `indexed_default=False`, el pago debió valorarse con la "
            "MISMA tasa que la factura -- no debió quedar ningún residual "
            "en moneda de compañía pese a que la tasa de mercado cambió "
            "entre la factura y el pago.",
        )

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
        ])
        self.assertFalse(
            notes,
            "No debió crearse ninguna ND/NC de diferencial cambiario: con "
            "`indexed_default=False` el pago se valora a la tasa de la "
            "factura, así que no hay diferencial que registrar.",
        )

    def _create_invoice_company_currency(self, invoice_date):
        """Mismo patrón que `_create_invoice`, pero la factura queda en la
        moneda DE COMPAÑÍA (VES) -- no se fuerza `currency_id`, el `Form`
        toma la que trae el diario de venta por defecto."""
        with Form(self.env["account.move"].with_context(default_move_type="out_invoice")) as inv_form:
            inv_form.partner_id = self.partner
            inv_form.invoice_date = invoice_date
            inv_form.journal_id = self.sale_journal
        invoice = inv_form.save()
        self.assertEqual(invoice.currency_id, self.company.currency_id)

        with Form(invoice) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.sale_product
                line.quantity = 1
                line.price_unit = 4000.0
        return inv_form_edit.save()

    def test_exchange_difference_settled_paying_ves_invoice_with_usd(self):
        """Caso inverso a `test_exchange_difference_settled_with_company_currency_payment`:
        factura en VES (moneda de COMPAÑÍA) pagada con el wizard
        'Registrar Pago' en USD, en una fecha posterior con tasa de cambio
        distinta -- reproduce el flujo real de "factura en bolívares,
        cliente paga en dólares".

        A diferencia de una factura en moneda EXTRANJERA (cuyo equivalente
        en VES sí fluctúa con la tasa entre la fecha de la factura y la
        del pago), una factura en VES tiene su monto FIJO -- no hay
        exposición cambiaria de su lado (`inv_rate` da 1.0 siempre, sin
        importar la fecha). Pagarla completa en USD, sea cual sea la tasa
        del día del pago, cierra exactamente en cero: no debe generarse
        NINGUNA ND/NC de diferencial cambiario. Este test confirma
        justamente eso -- que el módulo no genera una nota "fantasma"
        cuando matemáticamente no corresponde."""
        self.usd.write({
            "active": True,
            "rate_ids": [
                Command.create({
                    "name": "2034-01-01",
                    "company_rate": 1 / 40.0,
                }),
                Command.create({
                    "name": "2034-08-01",
                    "company_rate": 1 / 36.0,
                }),
            ],
        })

        invoice = self._create_invoice_company_currency("2034-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            # El wizard, por defecto, mantiene la moneda de la factura
            # (VES) sin importar la moneda del diario -- hay que forzar
            # explícitamente la moneda del PAGO a USD, tal como haría un
            # usuario que cambia ese campo en el formulario para pagar en
            # dólares una factura emitida en bolívares.
            pay_form.currency_id = self.usd
            pay_form.payment_date = "2034-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        self.assertEqual(payment_wizard.currency_id, self.usd)
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertFalse(
            notes,
            "Una factura en VES no debe generar ND/NC de diferencial cambiario, "
            "sin importar en qué moneda ni fecha se pague -- su monto no fluctúa con la tasa.",
        )

    def test_exchange_note_reversed_on_unreconcile(self):
        """Si se rompe la conciliación factura<->pago que originó la
        ND/NC (botón 'x' del widget de pagos, `js_remove_outstanding_partial`),
        la nota YA POSTEADA (con correlativo fiscal real) no puede
        simplemente cancelarse/borrarse -- debe revertirse, igual que hace
        Odoo con su propio asiento genérico de diferencial cambiario al
        desconciliar (`account.partial.reconcile.unlink()`: revierte si
        está posteado, borra si sigue en borrador)."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()
        invoice.invalidate_recordset()

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(notes), 1, "Debió crearse exactamente una ND/NC de diferencial cambiario.")
        note = notes[0]
        self.assertEqual(note.state, "posted")

        # Botón "x" del widget de pagos sobre la factura: rompe la
        # conciliación factura<->pago (no la de la nota contra la factura
        # o el pago, esa es una conciliación distinta).
        inv_line.invalidate_recordset()
        partial = (inv_line.matched_debit_ids | inv_line.matched_credit_ids).filtered(
            lambda p: invoice in (p.debit_move_id.move_id, p.credit_move_id.move_id)
        )
        self.assertTrue(partial, "Debía existir una conciliación factura<->pago para poder romperla.")
        invoice.js_remove_outstanding_partial(partial[:1].id)
        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()
        self.assertFalse(inv_line.reconciled, "La factura debió quedar desconciliada del pago.")

        # La nota original NO se cancela ni se borra (documento fiscal ya
        # posteado con correlativo real) -- sigue existiendo, posteada.
        note.invalidate_recordset()
        self.assertEqual(note.state, "posted")

        # Se creó una reversión de la nota, vinculada a ella y ya
        # conciliada/cerrada contra ella (cancel=True).
        reversal = self.env["account.move"].search([
            ("reversed_entry_id", "=", note.id),
        ])
        self.assertEqual(len(reversal), 1, "Debió crearse exactamente una reversión de la ND/NC.")
        self.assertEqual(reversal.state, "posted")
        self.assertTrue(reversal.l10n_ve_exchange_diff_entry)
        self.assertEqual(reversal.l10n_ve_exchange_original_id, note)

        # `note` es una NC DIRECTA en este escenario (tasas del
        # `setUpClass`: factura > pago). Revertirla produce un
        # `out_invoice` -- debe numerarse con la secuencia DEDICADA de
        # ND (viviendo en `debit_note_journal`), NUNCA con la secuencia
        # de FACTURAS del diario de venta normal (bug real: sin la
        # redirección de diario en `_reverse_moves`, la reversión
        # heredaba por copia el diario de la NC original -- el de venta
        # normal -- y salía numerada como una factura más).
        self.assertEqual(reversal.move_type, "out_invoice")
        self.assertEqual(
            reversal.journal_id, self.debit_note_journal,
            "La reversión de una NC directa debió redirigirse al diario "
            "dedicado de ND, no heredar el diario de venta de la NC original.",
        )
        self.assertTrue(
            reversal.name and reversal.name.startswith("NDDIFT/"),
            f"La reversión debió numerarse con la secuencia dedicada de ND, "
            f"no con la de facturas. name={reversal.name!r}",
        )

        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled, "La nota original debió quedar cerrada por su propia reversión.")

    def test_note_reversed_when_reconciliation_broken_via_remove_move_reconcile(self):
        """Misma reversión automática que `test_exchange_note_reversed_on_unreconcile`,
        pero rompiendo la conciliación factura<->pago por OTRA vía --
        `account.move.line.remove_move_reconcile()` directo (núcleo),
        NUNCA pasando por el botón del widget
        (`js_remove_outstanding_partial`). Antes de enganchar la
        reversión en `account.partial.reconcile.unlink()`
        (`models/account_partial_reconcile.py`) en vez de solo en el
        botón, romper la conciliación por esta vía dejaba la nota
        huérfana: posteada, con folio fiscal ya consumido, pero nunca
        revertida -- justo lo que hace `l10n_ve_igtf`
        (`cancel_advance_payment_transaction`) para cancelar pagos
        anticipados."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()
        invoice.invalidate_recordset()

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(notes), 1)
        note = notes[0]
        self.assertEqual(note.state, "posted")

        # `remove_move_reconcile()` -- NO el botón del widget -- opera
        # sobre la línea directamente, igual que hace
        # `l10n_ve_igtf.cancel_advance_payment_transaction` vía
        # `partial_reconcile.line_ids.remove_move_reconcile()` (nombre
        # de variable engañoso ahí: en realidad es un `account.move`, no
        # un `account.partial.reconcile`).
        inv_line.invalidate_recordset()
        inv_line.remove_move_reconcile()
        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()
        self.assertFalse(inv_line.reconciled, "La factura debió quedar desconciliada del pago.")

        note.invalidate_recordset()
        self.assertEqual(
            note.state, "posted",
            "La nota original no debió cancelarse ni borrarse (documento fiscal ya posteado).",
        )
        reversal = self.env["account.move"].search([
            ("reversed_entry_id", "=", note.id),
        ])
        self.assertEqual(
            len(reversal), 1,
            "Debió crearse una reversión de la ND/NC aunque la conciliación se "
            "rompió sin pasar por el botón del widget de pagos.",
        )
        self.assertEqual(reversal.state, "posted")

        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled, "La nota original debió quedar cerrada por su propia reversión.")

    def test_note_reversed_via_standard_reversal_wizard_keeps_dedicated_sequence(self):
        """`l10n_ve_exchange_diff_entry` tiene `copy=False`
        (`account_move.py`), y core arma la reversión con
        `move.copy(default_values)` (`account/models/account_move.py`)
        -- SIN pasarlo explícito en `default_values`, la reversión nace
        con el flag en `False`. `_reverse_exchange_note` (el único
        camino que ejercitan los demás tests de este archivo) SÍ lo pasa
        en su propio `default_values_list`, así que el bug quedaba
        oculto: revertir una nota por el wizard ESTÁNDAR de Odoo
        ("Reverse Entry", disponible en cualquier factura/NC posteada,
        ver `l10n_ve_donation.account_move.action_post` para otro uso ya
        existente de ese mismo wizard en este repo) NO pasa ese flag, y
        sin él el filtro de `_compute_name_by_sequence` no reconocía la
        reversión como propia -- caía al numerador normal del diario,
        consumiendo un correlativo ajeno (bug real, confirmado en
        runtime antes de este fix)."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))
        self.env.cr.flush()

        note = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(note), 1)
        self.assertEqual(note.move_type, "out_refund", "Precondición: tasas del setUpClass producen una NC directa.")

        # Wizard ESTÁNDAR de Odoo, no `_reverse_exchange_note` -- mismo
        # patrón que usa `l10n_ve_donation.account_move.action_post`.
        wizard = self.env["account.move.reversal"].with_context(
            active_ids=note.ids,
            active_model="account.move",
        ).create({"date": "2026-08-15", "journal_id": note.journal_id.id})
        wizard.reverse_moves()
        reversal = wizard.new_move_ids
        self.assertEqual(len(reversal), 1)
        reversal.with_context(move_action_post_alert=True).action_post()

        self.assertTrue(
            reversal.l10n_ve_exchange_diff_entry,
            "La reversión por el wizard estándar debió quedar marcada como "
            "propia de este módulo, igual que si se hubiera revertido por "
            "`_reverse_exchange_note`.",
        )
        self.assertEqual(reversal.l10n_ve_exchange_original_id, note)
        self.assertEqual(reversal.move_type, "out_invoice")
        self.assertEqual(
            reversal.journal_id, self.debit_note_journal,
            "La reversión (out_invoice) debió redirigirse al diario dedicado de ND.",
        )
        self.assertTrue(
            reversal.name and reversal.name.startswith("NDDIFT/"),
            f"La reversión debió numerarse con la secuencia dedicada de ND, "
            f"no con la de facturas. name={reversal.name!r}",
        )

    def test_reconciling_again_after_reversal_generates_new_note(self):
        """Continuación directa de `test_exchange_note_reversed_on_unreconcile`:
        tras romper la conciliación factura<->pago (revirtiendo la ND/NC
        original) y volver a asignar el MISMO pago pendiente a la
        factura (botón "Añadir" del widget de pagos,
        `js_assign_outstanding_line`), se debe generar una ND/NC NUEVA --
        el guard de duplicados de `_create_exchange_difference_note`
        buscaba por (factura, pago) con `state != 'cancel'` únicamente, y
        una nota YA REVERTIDA sigue `posted` (nunca se cancela, ver
        `_reverse_exchange_note`) -- sin excluir también las revertidas
        (`reversal_move_ids`), este segundo intento encontraba la nota
        vieja ya revertida y salía sin crear una nueva NI conciliar
        nada: la factura quedaba con un residual abierto sin ningún
        documento (ni ND/NC ni asiento genérico) que lo respaldara."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()
        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        original_note = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
            ("l10n_ve_exchange_payment_id", "=", payment.move_id.id),
        ])
        self.assertEqual(len(original_note), 1)

        # Rompe la conciliación factura<->pago -- revierte la ND/NC
        # original (queda `posted`, no `cancel`).
        partial = (inv_line.matched_debit_ids | inv_line.matched_credit_ids).filtered(
            lambda p: invoice in (p.debit_move_id.move_id, p.credit_move_id.move_id)
        )
        invoice.js_remove_outstanding_partial(partial[:1].id)
        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()
        original_note.invalidate_recordset()
        self.assertFalse(inv_line.reconciled, "La factura debió quedar desconciliada tras romper el partial.")
        self.assertEqual(original_note.state, "posted", "La ND/NC original sigue posteada -- solo revertida.")
        self.assertTrue(original_note.reversal_move_ids, "La ND/NC original debió quedar marcada como revertida.")

        # Vuelve a asignar el MISMO pago pendiente a la factura -- botón
        # "Añadir" del widget de pagos.
        payment_line = payment.move_id.line_ids.filtered(
            lambda l: l.account_type == "asset_receivable" and not l.reconciled
        )
        self.assertTrue(payment_line, "El pago debía quedar con su línea por cobrar disponible para re-asignar.")
        invoice.js_assign_outstanding_line(payment_line.id)
        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()
        self.assertTrue(
            inv_line.reconciled,
            "La factura debió quedar conciliada de nuevo al reasignar el mismo pago.",
        )
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes_after = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
            ("l10n_ve_exchange_payment_id", "=", payment.move_id.id),
        ])
        self.assertEqual(
            len(notes_after), 2,
            "Debió existir la ND/NC original (revertida) MÁS una ND/NC NUEVA para "
            "la re-conciliación -- el guard de duplicados no debe confundir una "
            "nota ya revertida con una todavía vigente.",
        )
        new_note = notes_after - original_note
        self.assertEqual(new_note.state, "posted")
        self.assertFalse(new_note.reversal_move_ids, "La ND/NC nueva no debe estar revertida.")
        new_note_line = new_note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(new_note_line.reconciled, "La ND/NC nueva debió quedar cerrada por su propia conciliación.")

    def test_break_reconcile_break_reverses_only_the_active_note(self):
        """Continuación de `test_reconciling_again_after_reversal_generates_new_note`:
        rompe->reconcilia->rompe de nuevo la MISMA factura contra el MISMO
        pago. `js_remove_outstanding_partial` localiza la nota a revertir
        buscando por (factura, pago, state != 'cancel') -- el MISMO patrón
        que tenía el guard de duplicados de `_create_exchange_difference_note`
        antes de su fix (bloqueante ya corregido). Sin excluir también
        `reversal_move_ids`, esa búsqueda puede encontrar la nota VIEJA ya
        revertida (sigue `posted`, nunca pasa a `cancel`) en vez de la nota
        NUEVA vigente, revirtiendo la vieja una segunda vez en lugar de la
        que corresponde.

        NOTA: `js_remove_outstanding_partial` fija `order='id desc'`
        explícito en su búsqueda (no depende del orden por defecto de
        `account.move`, `date desc, name desc, ..., id desc`, que además
        coincidiría por casualidad con `id desc` en este caso ya que la
        nota nueva siempre tiene fecha/nombre posteriores a la vieja) --
        por eso esta prueba, ADEMÁS de ejercitar el flujo de negocio
        completo, verifica el DOMINIO de búsqueda por separado
        (`test_search_domain_for_active_note_excludes_reversed_notes`,
        más abajo), que es donde el bug realmente vivía: sin el filtro
        `reversal_move_ids`, ese dominio devolvería 2 notas en vez de 1,
        sin importar el orden que se use para desempatar."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()
        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        original_note = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
            ("l10n_ve_exchange_payment_id", "=", payment.move_id.id),
        ])
        self.assertEqual(len(original_note), 1)

        # Primera ruptura: revierte la nota original.
        partial = (inv_line.matched_debit_ids | inv_line.matched_credit_ids).filtered(
            lambda p: invoice in (p.debit_move_id.move_id, p.credit_move_id.move_id)
        )
        invoice.js_remove_outstanding_partial(partial[:1].id)
        self.env.cr.flush()
        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()
        original_note.invalidate_recordset()
        self.assertTrue(original_note.reversal_move_ids, "La nota original debió quedar revertida.")

        # Vuelve a asignar el mismo pago -- genera la ND/NC nueva.
        payment_line = payment.move_id.line_ids.filtered(
            lambda l: l.account_type == "asset_receivable" and not l.reconciled
        )
        invoice.js_assign_outstanding_line(payment_line.id)
        self.env.cr.flush()
        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        new_note = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
            ("l10n_ve_exchange_payment_id", "=", payment.move_id.id),
        ]) - original_note
        self.assertEqual(len(new_note), 1)
        self.assertFalse(new_note.reversal_move_ids)

        # Segunda ruptura: debe revertir la nota NUEVA (la única vigente),
        # y NO tocar de nuevo la original (ya revertida).
        new_partial = (inv_line.matched_debit_ids | inv_line.matched_credit_ids).filtered(
            lambda p: invoice in (p.debit_move_id.move_id, p.credit_move_id.move_id)
        )
        invoice.js_remove_outstanding_partial(new_partial[:1].id)
        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()
        original_note.invalidate_recordset()
        new_note.invalidate_recordset()

        self.assertFalse(inv_line.reconciled, "La factura debió quedar desconciliada tras la segunda ruptura.")
        self.assertTrue(new_note.reversal_move_ids, "La ND/NC nueva debió quedar revertida por la segunda ruptura.")

        original_reversals = self.env["account.move"].search([
            ("reversed_entry_id", "=", original_note.id),
        ])
        self.assertEqual(
            len(original_reversals), 1,
            "La nota original solo debe tener UNA reversión -- la segunda ruptura no "
            "debe generar una segunda reversión sobre una nota que ya estaba revertida.",
        )

        new_note_reversals = self.env["account.move"].search([
            ("reversed_entry_id", "=", new_note.id),
        ])
        self.assertEqual(
            len(new_note_reversals), 1,
            "La ND/NC nueva debió recibir exactamente una reversión propia por la segunda ruptura.",
        )

    def test_search_domain_for_active_note_excludes_reversed_notes(self):
        """Verifica el DOMINIO de búsqueda que usa `js_remove_outstanding_partial`
        (y, de forma simétrica, `_create_exchange_difference_note`) de
        forma aislada, sin depender de qué `order` se use para desempatar
        -- el bug real no era de orden, era que sin el filtro
        `reversal_move_ids` el dominio devuelve 2 registros (la original
        revertida MÁS la nueva) en vez de 1. Este es el caso que
        realmente importa: si algún día se relaja el guard y llegan a
        coexistir dos notas activas por error, esta prueba lo detecta
        directamente en el dominio, sin necesidad de mockear ordenamiento
        interno del framework (frágil para mantenimiento)."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))
        self.env.cr.flush()
        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        original_note = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
            ("l10n_ve_exchange_payment_id", "=", payment.move_id.id),
        ])
        self.assertEqual(len(original_note), 1)

        partial = (inv_line.matched_debit_ids | inv_line.matched_credit_ids).filtered(
            lambda p: invoice in (p.debit_move_id.move_id, p.credit_move_id.move_id)
        )
        invoice.js_remove_outstanding_partial(partial[:1].id)
        self.env.cr.flush()
        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()
        original_note.invalidate_recordset()
        self.assertTrue(original_note.reversal_move_ids)

        payment_line = payment.move_id.line_ids.filtered(
            lambda l: l.account_type == "asset_receivable" and not l.reconciled
        )
        invoice.js_assign_outstanding_line(payment_line.id)
        self.env.cr.flush()
        invoice.invalidate_recordset()

        new_note = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
            ("l10n_ve_exchange_payment_id", "=", payment.move_id.id),
        ]) - original_note
        self.assertEqual(len(new_note), 1)

        # Sin el filtro `reversal_move_ids`, este dominio devolvería 2
        # registros (original_note + new_note) -- CON el filtro, debe
        # devolver exactamente 1: la nueva.
        active_notes_by_domain = self.env["account.move"].search([
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
            ("l10n_ve_exchange_payment_id", "=", payment.move_id.id),
            ("state", "!=", "cancel"),
            ("reversal_move_ids", "=", False),
        ])
        self.assertEqual(
            active_notes_by_domain, new_note,
            "El dominio de búsqueda de la nota activa debió resolver a exactamente "
            "1 registro (la nota nueva) -- si incluye también la original ya "
            "revertida, el guard anti-duplicado dejó de ser efectivo.",
        )

    def test_exchange_note_own_reconciliation_cannot_be_broken_directly(self):
        """La conciliación que cierra la ND/NC contra la factura/pago NO
        se puede romper suelta -- ni haciendo click desde la propia nota,
        ni desde la factura viendo esa reconciliación puntual en su lista
        de pagos. Solo debe deshacerse como consecuencia de romper la
        conciliación ORIGINAL factura<->pago (ver
        `test_exchange_note_reversed_on_unreconcile`)."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(notes), 1, "Debió crearse exactamente una ND/NC de diferencial cambiario.")
        note = notes[0]
        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        # La conciliación que cierra la nota (nota <-> factura/pago, según
        # la rama), vista desde la propia nota.
        note_partial = note_line.matched_debit_ids | note_line.matched_credit_ids
        self.assertTrue(note_partial, "La nota debía quedar conciliada contra la factura/pago.")

        with self.assertRaises(UserError):
            note.js_remove_outstanding_partial(note_partial[:1].id)

        # Mismo bloqueo visto desde el OTRO lado de esa conciliación
        # puntual (la factura o el pago, según a cuál se ligó la nota).
        other_move = (note_partial[:1].debit_move_id.move_id | note_partial[:1].credit_move_id.move_id) - note
        if other_move:
            with self.assertRaises(UserError):
                other_move.js_remove_outstanding_partial(note_partial[:1].id)

        # Nada se rompió: la nota sigue conciliada y posteada.
        note.invalidate_recordset()
        note_line.invalidate_recordset()
        self.assertEqual(note.state, "posted")
        self.assertTrue(note_line.reconciled)

    def test_exchange_difference_credit_note_branch(self):
        """Mismo flujo (factura USD -> 'Registrar Pago' vía Form -> pago USD
        en fecha con tasa distinta), con tasa de la factura MAYOR que la
        del pago -- residual = matched_amount * (inv_rate - pay_rate) > 0
        -> rama de residual en DÉBITO ("falta") -> Nota de Crédito."""
        self.usd.write({
            "active": True,
            "rate_ids": [
                Command.create({
                    "name": "2027-01-01",
                    "company_rate": 1 / 40.0,
                }),
                Command.create({
                    "name": "2027-08-01",
                    "company_rate": 1 / 36.0,
                }),
            ],
        })

        invoice = self._create_invoice("2027-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2027-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))
        payment.action_post()

        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(notes), 1, "Debió crearse exactamente una ND/NC de diferencial cambiario.")
        note = notes[0]
        self.assertEqual(note.state, "posted")
        self.assertEqual(note.l10n_ve_exchange_invoice_id, invoice)
        self.assertTrue(
            note.l10n_ve_exchange_is_credit_note,
            "Con la tasa de la factura menor que la del pago, se esperaba la rama de Nota de Crédito.",
        )
        self.assertEqual(note.move_type, "out_refund")
        self.assertEqual(note.reversed_entry_id, invoice)
        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(note_line.amount_residual))

        # Clasificación correcta: esta SÍ es una NC propia de diferencial,
        # nunca una ND (ver `_is_exchange_debit_note`/`_is_exchange_credit_note`,
        # `models/account_move.py`).
        self.assertTrue(note._is_exchange_credit_note())
        self.assertFalse(note._is_exchange_debit_note())

        # Fechada el día del PAGO (2027-08-01), no el día en que corre el
        # test (`context_today()`).
        self.assertEqual(note.date, fields.Date.from_string("2027-08-01"))
        self.assertEqual(note.l10n_ve_exchange_payment_id, payment.move_id)

        # `invoice_date_display` (la fecha que se IMPRIME en el
        # documento) también debe quedar en la fecha del pago -- sin
        # setearla explícito, Odoo la deja en blanco y el reporte impreso
        # cae al día en que se corre/imprime (HOY), no al de la nota.
        self.assertEqual(note.invoice_date_display, fields.Date.from_string("2027-08-01"))

        # `foreign_rate` de la NC debe reflejar la tasa a la fecha DEL
        # PAGO (2027-08-01), NO la de la factura -- sin el override en
        # `_create_exchange_difference_note`, `l10n_ve_accountant`
        # (`account_move.create()`) hereda `foreign_rate` de
        # `reversed_entry_id` incondicionalmente para cualquier
        # `out_refund`/`in_refund`, dejando la NC con la tasa VIEJA de la
        # factura en vez de la del pago -- asimétrico respecto a la ND
        # (que sí calcula su propia tasa natural, porque nace de
        # `debit_origin_id`, no de `reversed_entry_id`).
        expected_rate_values = self.env["res.currency.rate"].compute_rate(
            self.usd.id, fields.Date.from_string("2027-08-01"),
        )
        self.assertAlmostEqual(
            note.foreign_rate, expected_rate_values.get("foreign_rate", 0), places=6,
            msg="La NC debió tomar la tasa vigente a la fecha DEL PAGO, no la de la factura.",
        )
        self.assertNotAlmostEqual(
            note.foreign_rate, invoice.foreign_rate, places=6,
            msg="La NC no debió heredar la tasa de la factura (serían iguales solo por "
            "coincidencia con estas tasas deliberadamente distintas).",
        )

        # La NC de PÉRDIDA debe acreditar la cuenta de pérdida cambiaria de
        # la compañía, NUNCA la cuenta de ingreso del producto (que
        # `_check_l10n_ve_exchange_note_product_id` fuerza a ser la de
        # GANANCIA) -- `is_sale_document()` del núcleo trata `out_refund`
        # igual que `out_invoice` al resolver la cuenta de la línea, así
        # que sin el override explícito de `account_id` en
        # `_create_exchange_difference_note` esta NC terminaría
        # acreditando la cuenta de ganancia.
        product_line = note.line_ids.filtered(lambda l: l.display_type == "product")
        self.assertEqual(
            product_line.account_id, self.company.expense_currency_exchange_account_id,
            "La Nota de Crédito de pérdida cambiaria debió usar la cuenta de pérdida, no la de ganancia.",
        )

    def test_exchange_difference_debit_note_branch(self):
        """Mismo flujo, con tasa de la factura MENOR que la del pago --
        residual = matched_amount * (inv_rate - pay_rate) < 0 -> rama de
        residual en CRÉDITO ("sobra"/ganancia) -> Nota de Débito vía
        `account.debit.note` (con `debit_origin_id`)."""
        self.usd.write({
            "active": True,
            "rate_ids": [
                Command.create({
                    "name": "2029-01-01",
                    "company_rate": 1 / 36.0,
                }),
                Command.create({
                    "name": "2029-08-01",
                    "company_rate": 1 / 40.0,
                }),
            ],
        })

        invoice = self._create_invoice("2029-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2029-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))
        payment.action_post()

        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(notes), 1, "Debió crearse exactamente una ND/NC de diferencial cambiario.")
        note = notes[0]
        self.assertEqual(note.state, "posted")
        self.assertEqual(note.l10n_ve_exchange_invoice_id, invoice)
        self.assertFalse(
            note.l10n_ve_exchange_is_credit_note,
            "Con la tasa de la factura mayor que la del pago, se esperaba la rama de Nota de Débito.",
        )
        self.assertEqual(note.move_type, "out_invoice")
        self.assertEqual(note.debit_origin_id, invoice)

        # Numerada con el AÑO DE SU PROPIA FECHA (2029, la del pago), no
        # el de hoy: `cls.debit_note_sequence` (`setUpClass`) NO tiene
        # `use_date_range=True` -- justo el caso donde
        # `ir.sequence.next_by_id(sequence_date=...)` por sí solo NO
        # alcanza (core solo respeta ese kwarg cuando la secuencia usa
        # rangos por fecha; si no, interpola el prefijo con
        # `datetime.now()` salvo que la fecha venga por contexto
        # `ir_sequence_date`, ver `_compute_name_by_sequence`).
        self.assertTrue(
            note.name.startswith("NDDIFT/2029/"),
            f"La ND debió numerarse con el año de su propia fecha (2029), "
            f"no el de hoy. name={note.name!r}",
        )

        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(note_line.amount_residual))

        # Clasificación correcta: esta SÍ es una ND propia de diferencial,
        # nunca una NC (ver `_is_exchange_debit_note`/`_is_exchange_credit_note`,
        # `models/account_move.py`).
        self.assertTrue(note._is_exchange_debit_note())
        self.assertFalse(note._is_exchange_credit_note())

        # Fechada el día del PAGO (2029-08-01), no el día en que corre el
        # test.
        self.assertEqual(note.date, fields.Date.from_string("2029-08-01"))
        self.assertEqual(note.l10n_ve_exchange_payment_id, payment.move_id)

        # La ND de GANANCIA debe acreditar la cuenta de ganancia cambiaria
        # de la compañía (la que exige el producto vía
        # `_check_l10n_ve_exchange_note_product_id`).
        product_line = note.line_ids.filtered(lambda l: l.display_type == "product")
        self.assertEqual(
            product_line.account_id, self.company.income_currency_exchange_account_id,
            "La Nota de Débito de ganancia cambiaria debió usar la cuenta de ganancia.",
        )

    def test_exchange_note_debit_note_reversed_on_unreconcile(self):
        """La reversión al desconciliar (ver
        `test_exchange_note_reversed_on_unreconcile`) también debe
        funcionar cuando la nota original es una ND (Nota de Débito, no
        NC) -- confirma que `_reverse_moves` (con su ajuste propio para
        `_is_exchange_debit_note()`, ver `models/account_move.py`) deja
        `l10n_ve_exchange_original_id` apuntando a la ND revertida."""
        self.usd.write({
            "active": True,
            "rate_ids": [
                Command.create({
                    "name": "2030-01-01",
                    "company_rate": 1 / 36.0,
                }),
                Command.create({
                    "name": "2030-08-01",
                    "company_rate": 1 / 40.0,
                }),
            ],
        })

        invoice = self._create_invoice("2030-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2030-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()
        invoice.invalidate_recordset()

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(notes), 1)
        note = notes[0]
        self.assertFalse(note.l10n_ve_exchange_is_credit_note, "Este caso debía producir una ND.")
        self.assertEqual(note.state, "posted")

        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        partial = (inv_line.matched_debit_ids | inv_line.matched_credit_ids).filtered(
            lambda p: invoice in (p.debit_move_id.move_id, p.credit_move_id.move_id)
        )
        self.assertTrue(partial, "Debía existir una conciliación factura<->pago para poder romperla.")
        invoice.js_remove_outstanding_partial(partial[:1].id)
        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()
        self.assertFalse(inv_line.reconciled, "La factura debió quedar desconciliada del pago.")

        # La ND original no se cancela ni se borra -- sigue posteada.
        note.invalidate_recordset()
        self.assertEqual(note.state, "posted")

        # Se creó una reversión (Nota de Crédito, `move_type` se invierte
        # de `out_invoice` a `out_refund`), vinculada a la ND vía
        # `l10n_ve_exchange_original_id` (no `reversed_entry_id` -- ese
        # campo lo usa Odoo para la reversión NATIVA de un documento
        # cualquiera; `l10n_ve_exchange_original_id` es el que usamos
        # específicamente para "esta NC revierte aquella ND de
        # diferencial").
        reversal = self.env["account.move"].search([
            ("l10n_ve_exchange_original_id", "=", note.id),
        ])
        self.assertEqual(len(reversal), 1, "Debió crearse exactamente una reversión de la ND.")
        self.assertEqual(reversal.state, "posted")
        self.assertEqual(reversal.move_type, "out_refund")
        self.assertTrue(reversal.l10n_ve_exchange_diff_entry)

        # La reversión (con `l10n_ve_exchange_original_id` apuntando a la
        # ND) debe clasificar como NC de diferencial, nunca como ND -- y la
        # ND original, ya cerrada por su propia reversión, sigue
        # clasificando como ND (el campo `original_id` va en la reversión,
        # no en la nota original).
        self.assertTrue(reversal._is_exchange_credit_note())
        self.assertFalse(reversal._is_exchange_debit_note())
        self.assertTrue(note._is_exchange_debit_note())
        self.assertFalse(note._is_exchange_credit_note())

        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled, "La ND original debió quedar cerrada por su propia reversión.")

    def test_exchange_use_nd_nc_disabled_uses_native_exchange_entry(self):
        """Con `l10n_ve_exchange_use_nd_nc` desactivado, `reconcile()` no
        debe aplicar ninguna lógica propia -- cae directo al
        `super().reconcile()` nativo de Odoo (con su propio asiento
        genérico de diferencial, sin el context `no_exchange_difference`),
        y no debe crearse ninguna ND/NC nuestra."""
        self.company.l10n_ve_exchange_use_nd_nc = False

        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))
        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertFalse(notes, "Con el modo ND/NC desactivado no debió crearse ninguna nota nuestra.")

    def test_toggle_without_product_raises_at_save_time(self):
        """Con el toggle activo, quitar el producto de diferencial
        cambiario (`res.company.l10n_ve_exchange_note_product_id`) NO se
        puede guardar -- `_check_l10n_ve_exchange_use_nd_nc_requires_config`
        lo bloquea en el momento de guardar la compañía, antes de que
        nadie llegue a pagar una factura con esa configuración a medias
        (ver `test_toggle_without_pricelist_raises_at_save_time` para la
        misma regla sobre la lista de precios, y
        `test_missing_note_product_raises_user_error_defense_in_depth`
        para el guard adicional en tiempo de conciliación, por si ese
        estado inconsistente llega a existir en la base de datos por
        cualquier otra vía distinta al ORM)."""
        with self.assertRaises(ValidationError):
            self.company.l10n_ve_exchange_note_product_id = False

    def test_missing_note_product_raises_user_error_defense_in_depth(self):
        """Si, pese al constraint de guardado, la compañía llegara a
        quedar con el toggle activo y sin producto configurado (ej. un
        estado preexistente escrito antes de que este constraint
        existiera, o por SQL directo) -- no se debe crear una nota "a
        medias": debe fallar con un `UserError` claro al intentar pagar
        (ver `_create_exchange_difference_note`). Se simula ese estado
        con SQL directo, saltándose el constraint del ORM a propósito,
        para ejercitar este segundo guard independiente."""
        self.env.cr.execute(
            "UPDATE res_company SET l10n_ve_exchange_note_product_id = NULL WHERE id = %s",
            (self.company.id,),
        )
        self.company.invalidate_recordset()
        self.assertFalse(self.company.l10n_ve_exchange_note_product_id)

        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record

        # La ND/NC se crea de forma SÍNCRONA dentro de la propia
        # transacción de conciliación (`_create_exchange_difference_moves`,
        # ver `account_move_line.py`) -- el error se dispara directo
        # desde `action_create_payments()`, no en un `flush()` posterior.
        with self.assertRaises(UserError):
            payment_wizard.action_create_payments()

    def test_payment_side_counterpart_is_always_same_account_as_invoice_receivable(self):
        """Documenta por qué el filtro `account_type == 'asset_receivable'`
        sobre `payment_lines` (línea 50-52 de `reconcile()`) NUNCA puede
        vaciarse cuando `invoice_lines` no está vacío -- no es una
        suposición, es una garantía que impone el propio `reconcile()`
        NATIVO de Odoo, verificada acá construyendo el escenario que en
        teoría lo rompería: una línea de factura (`asset_receivable`)
        conciliada DIRECTO contra una línea en una cuenta DISTINTA
        (`liability_current`, ej. una cuenta de anticipo, sin pasar por
        el asiento puente `asset_receivable` que usa el mecanismo real
        de anticipos de `l10n_ve_igtf` -- ver
        `test_advance_payment_applied_to_two_invoices_each_gets_correct_note`).

        El propio núcleo de Odoo (`account/models/account_move_line.py`,
        `reconcile()`) EXIGE que todas las líneas a conciliar compartan
        la MISMA `account_id` -- lanza `UserError` ("Entries are not
        from the same account") antes de cualquier otra lógica, sin
        importar el `account_type`. Como `account_type` es una
        propiedad de la CUENTA (no de la línea), si `invoice_lines` ya
        es `asset_receivable`, cualquier otra línea que sobreviva ese
        chequeo del núcleo está forzosamente en ESA MISMA cuenta -- por
        lo tanto también `asset_receivable`. El filtro de `payment_lines`
        es, en este punto exacto del flujo, tautológicamente imposible
        de vaciar."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        # Fallback de creación -- sin esto, en una base sin ese tipo de
        # cuenta ya configurado (ej. `lloro`), `search()` devuelve vacío y
        # la línea del asiento contrapartida queda con `account_id=NULL`,
        # reventando el `CHECK account_move_line_check_accountable_required_fields`
        # de Postgres antes de siquiera llegar al `reconcile()` que este
        # test existe para probar.
        liability_account = self.env["account.account"].search(
            [
                *self.env["account.account"]._check_company_domain(self.company),
                ("account_type", "=", "liability_current"),
            ],
            limit=1,
        )
        if not liability_account:
            liability_account = self.env["account.account"].create({
                "name": "Pasivo Corriente Prueba Reversal",
                "code": "2401REV",
                "account_type": "liability_current",
                "company_ids": [Command.set([self.company.id])],
            })
        income = self.env["account.account"].search(
            [*self.env["account.account"]._check_company_domain(self.company), ("account_type", "=", "income")],
            limit=1,
        )
        if not income:
            income = self.env["account.account"].create({
                "name": "Ingresos Contrapartida Prueba Reversal",
                "code": "4003REV",
                "account_type": "income",
                "company_ids": [Command.set([self.company.id])],
            })
        counterpart_entry = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.sale_journal.id,
            "date": "2026-08-01",
            "line_ids": [
                (0, 0, {
                    "account_id": liability_account.id, "partner_id": self.partner.id,
                    "currency_id": self.usd.id, "amount_currency": -100.0,
                    "debit": 0.0, "credit": self.rate_payment_date * 100.0,
                }),
                (0, 0, {
                    "account_id": income.id, "partner_id": self.partner.id,
                    "debit": self.rate_payment_date * 100.0, "credit": 0.0,
                }),
            ],
        })
        counterpart_entry.action_post()
        counterpart_line = counterpart_entry.line_ids.filtered(
            lambda l: l.account_id == liability_account
        )

        with self.assertRaises(UserError):
            (inv_line + counterpart_line).reconcile()

    def test_note_without_receivable_line_raises_instead_of_silently_orphaning(self):
        """Defensa en profundidad en `_create_exchange_difference_note`
        (`account_move_line.py`): si la nota recién creada/posteada NO
        tuviera línea `asset_receivable` (nunca debería pasar para un
        `out_invoice`/`out_refund` con línea de producto -- Odoo siempre
        la agrega al postear), un `.write()` sobre un recordset VACÍO no
        haría nada ni lanzaría error: la nota quedaría posteada
        (correlativo fiscal ya consumido) pero sin conciliar contra la
        factura/pago, con el residual cambiario abierto y sin ningún
        aviso. Se simula ese estado imposible parcheando `filtered` para
        que devuelva vacío SOLO para el filtro de `account_type ==
        'asset_receivable'` sobre la nota recién creada -- confirma que
        el guard nuevo lanza `UserError` en vez de dejar la nota huérfana
        en silencio."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()

        AccountMoveLine = type(self.env["account.move.line"])
        original_filtered = AccountMoveLine.filtered

        def fake_filtered(self_lines, func):
            result = original_filtered(self_lines, func)
            if (
                result
                and all(l.move_id.l10n_ve_exchange_diff_entry for l in result)
                and all(l.account_type == "asset_receivable" for l in result)
            ):
                return self.env["account.move.line"]
            return result

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record

        with patch.object(AccountMoveLine, "filtered", fake_filtered):
            with self.assertRaises(UserError):
                payment_wizard.action_create_payments()

    def _create_note_product(self, name, **overrides):
        """Crea un producto con la MISMA configuración base válida que
        `cls.note_product` (servicio, cuentas de ganancia/pérdida
        cambiaria, impuesto exento por defecto), con `overrides` para
        romper deliberadamente una sola condición a la vez. Se usa
        `create()` explícito y NO `.copy()`: `product.product.copy()` no
        propaga de forma confiable un `type` distinto al del original
        (confirmado con un script de depuración -- el campo queda en
        `False` en vez del valor pedido), lo que hacía que los tests
        negativos de tipo pasaran en falso positivo sin ejercitar el
        constraint."""
        vals = {
            "name": name,
            "type": "service",
            "taxes_id": [(6, 0, self.exent.ids)],
            # Explícito por la misma razón documentada en `setUpClass` al
            # crear `cls.note_product`: sin esto, el default de Odoo para
            # `supplier_taxes_id` puede traer más de un impuesto de compra
            # al 0% en bases con varios configurados, y
            # `_enforce_single_tax_vals` (`l10n_ve_accountant`) rechaza
            # cualquier producto con más de un impuesto de compra asignado.
            "supplier_taxes_id": [(6, 0, self.exent_purchase.ids)],
            "property_account_income_id": self.company.income_currency_exchange_account_id.id,
            "property_account_expense_id": self.company.expense_currency_exchange_account_id.id,
        }
        vals.update(overrides)
        return self.env["product.product"].create(vals)

    def test_note_product_must_be_a_service(self):
        """`l10n_ve_exchange_note_product_id` rechaza un producto que no
        sea de tipo servicio (`_check_l10n_ve_exchange_note_product_id`,
        `models/res_company.py`)."""
        bad_product = self._create_note_product("Diferencial Test No Servicio", type="consu")
        with self.assertRaises(ValidationError):
            self.company.write({"l10n_ve_exchange_note_product_id": bad_product.id})

    def test_note_product_must_use_company_exchange_gain_account_as_income(self):
        """`l10n_ve_exchange_note_product_id` rechaza un producto cuya
        cuenta de ingreso NO sea la cuenta de ganancia cambiaria de la
        compañía (`company.income_currency_exchange_account_id`)."""
        # Creada explícita, no buscada: un `search()` de "otra cuenta de
        # ingreso" depende de que la base ya traiga alguna configurada
        # -- en un entorno sin chart of accounts previo no hay ninguna,
        # el `search()` da vacío, y `property_account_income_id=False`
        # deja pasar el producto en falso positivo sin ejercitar el
        # constraint (el test pasaba "sin querer" solo porque no había
        # datos, no porque la validación funcionara).
        other_income = self.env["account.account"].create({
            "name": "Otro Ingreso Prueba Reversal",
            "code": "4002REV",
            "account_type": "income",
            "company_ids": [Command.set([self.company.id])],
        })
        bad_product = self._create_note_product(
            "Diferencial Test Cuenta Ingreso Incorrecta",
            property_account_income_id=other_income.id,
        )
        with self.assertRaises(ValidationError):
            self.company.write({"l10n_ve_exchange_note_product_id": bad_product.id})

    def test_note_product_must_use_company_exchange_loss_account_as_expense(self):
        """`l10n_ve_exchange_note_product_id` rechaza un producto cuya
        cuenta de gasto NO sea la cuenta de pérdida cambiaria de la
        compañía (`company.expense_currency_exchange_account_id`)."""
        # Creada explícita -- mismo motivo que en el test de la cuenta
        # de ingreso (arriba): un `search()` de "otra cuenta de gasto"
        # depende de datos preexistentes que no hay en un entorno sin
        # chart of accounts previo.
        other_expense = self.env["account.account"].create({
            "name": "Otro Gasto Prueba Reversal",
            "code": "5002REV",
            "account_type": "expense",
            "company_ids": [Command.set([self.company.id])],
        })
        bad_product = self._create_note_product(
            "Diferencial Test Cuenta Gasto Incorrecta",
            property_account_expense_id=other_expense.id,
        )
        with self.assertRaises(ValidationError):
            self.company.write({"l10n_ve_exchange_note_product_id": bad_product.id})

    def test_note_product_must_use_default_sale_exempt_tax(self):
        """`l10n_ve_exchange_note_product_id` rechaza un producto cuyo
        impuesto de venta NO sea el exento por defecto de la compañía
        (`company.exent_aliquot_sale`) -- ej. un impuesto distinto."""
        # Un impuesto DISTINTO, no vacío -- `taxes_id=[(5,0,0)]` (sin
        # impuesto alguno) revienta antes, en `_enforce_single_tax_vals`
        # (`l10n_ve_accountant`), que exige exactamente un impuesto de
        # venta cuando la compañía no tiene fiscal position por
        # defecto -- eso probaba OTRO guard, nunca llegaba al que este
        # test dice ejercitar.
        other_sale_tax = self.env['account.tax'].create({
            'name': 'IVA Distinto Prueba Reversal',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'company_id': self.company.id,
            'tax_group_id': self.exent_tax_group.id,
            'country_id': self.company.country_id.id,
        })
        bad_product = self._create_note_product(
            "Diferencial Test Impuesto Incorrecto", taxes_id=[(6, 0, other_sale_tax.ids)],
        )
        with self.assertRaises(ValidationError):
            self.company.write({"l10n_ve_exchange_note_product_id": bad_product.id})

    def test_note_product_passing_full_domain_is_accepted(self):
        """Control positivo: un producto que sí cumple las 3 condiciones
        (servicio, cuentas de ganancia/pérdida cambiaria, impuesto exento
        por defecto) se acepta sin error -- confirma que el constraint no
        es sobre-restrictivo con la configuración correcta (la misma que
        usa `cls.note_product` en `setUpClass`)."""
        good_product = self._create_note_product("Diferencial Test Reversal (válido)")
        self.company.write({"l10n_ve_exchange_note_product_id": good_product.id})
        self.assertEqual(self.company.l10n_ve_exchange_note_product_id, good_product)

    def test_note_pricelist_must_be_in_company_currency(self):
        """`l10n_ve_exchange_note_pricelist_id` rechaza una lista de
        precios en cualquier moneda distinta a la de la compañía (VEF) --
        las ND/NC de diferencial siempre se crean en moneda de compañía
        (`_check_l10n_ve_exchange_note_pricelist_id`, `models/res_company.py`)."""
        bad_pricelist = self.env["product.pricelist"].create({
            "name": "Diferencial Test Reversal (USD, inválida)",
            "currency_id": self.usd.id,
        })
        with self.assertRaises(ValidationError):
            self.company.write({"l10n_ve_exchange_note_pricelist_id": bad_pricelist.id})

    def test_note_pricelist_in_company_currency_is_accepted(self):
        """Control positivo: una lista de precios en la moneda de la
        compañía se acepta sin error (la misma configuración que usa
        `cls.note_pricelist` en `setUpClass`)."""
        good_pricelist = self.env["product.pricelist"].create({
            "name": "Diferencial Test Reversal (VEF, válida)",
            "currency_id": self.company.currency_id.id,
        })
        self.company.write({"l10n_ve_exchange_note_pricelist_id": good_pricelist.id})
        self.assertEqual(self.company.l10n_ve_exchange_note_pricelist_id, good_pricelist)

    def test_toggle_without_pricelist_raises_at_save_time(self):
        """Con el toggle activo, quitar la lista de precios de diferencial
        cambiario NO se puede guardar -- mismo constraint de guardado que
        `test_toggle_without_product_raises_at_save_time`, esta vez sobre
        `l10n_ve_exchange_note_pricelist_id`."""
        with self.assertRaises(ValidationError):
            self.company.l10n_ve_exchange_note_pricelist_id = False

    def test_missing_note_pricelist_raises_user_error_defense_in_depth(self):
        """Mismo guard adicional en tiempo de conciliación que
        `test_missing_note_product_raises_user_error_defense_in_depth`,
        esta vez para la lista de precios -- no se debe crear una nota
        "a medias" si ese estado inconsistente llega a existir en la
        base de datos por una vía distinta al ORM."""
        self.env.cr.execute(
            "UPDATE res_company SET l10n_ve_exchange_note_pricelist_id = NULL WHERE id = %s",
            (self.company.id,),
        )
        self.company.invalidate_recordset()
        self.assertFalse(self.company.l10n_ve_exchange_note_pricelist_id)

        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record

        with self.assertRaises(UserError):
            payment_wizard.action_create_payments()

    def test_duplicate_call_does_not_create_duplicate_note(self):
        """Dos conciliaciones casi simultáneas contra la misma factura
        (doble clic, o un batch de pagos) podrían intentar crear una
        ND/NC dos veces para el mismo par (factura, pago) -- la segunda
        NO debe generar una ND/NC duplicada. Se reproduce llamando al
        método directamente una segunda vez para la misma factura (ver el
        guard de `existing_note` en `_create_exchange_difference_note`,
        `models/account_move_line.py`)."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()
        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(notes), 1, "Debió crearse exactamente una ND/NC de diferencial cambiario.")

        # Simula una segunda llamada para la misma factura/pago: el monto
        # del residual es irrelevante para el guard, que corta ANTES de
        # mirarlo -- alcanza con que ya exista una nota no cancelada
        # vinculada a `invoice`. Se pasa `payment.move_id` (el asiento
        # contable del pago), no el `account.payment` en sí -- `id` de
        # ambos NO coincide (`account.payment` delega en `account.move`
        # vía `_inherits`) y así es como `reconcile()` lo resuelve
        # realmente (`payment_line.move_id`).
        inv_line._create_exchange_difference_note(invoice, payment.move_id, 1.0)

        notes_after = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(
            len(notes_after), 1,
            "La segunda llamada para la misma factura/pago no debió crear una ND/NC duplicada.",
        )

    def test_debit_note_uses_dedicated_journal_credit_note_uses_invoice_journal(self):
        """El diario dedicado de ND (`is_debit=True`, `type='sale'`) solo
        debe usarse en la rama de Nota de DÉBITO -- la rama de Nota de
        CRÉDITO debe seguir usando el propio diario de venta de la factura
        de origen (Odoo ya provee `refund_sequence_id` ahí para numerar
        NC), nunca el diario dedicado de ND."""
        debit_journal = self.debit_note_journal

        # Rama de Nota de Débito (tasa de la factura MENOR que la del
        # pago -- mismas tasas que `test_exchange_difference_debit_note_branch`).
        self.usd.write({
            "active": True,
            "rate_ids": [
                Command.create({
                    "name": "2031-01-01",
                    "company_rate": 1 / 36.0,
                }),
                Command.create({
                    "name": "2031-08-01",
                    "company_rate": 1 / 40.0,
                }),
            ],
        })
        invoice_debit = self._create_invoice("2031-01-01")
        invoice_debit.with_context(move_action_post_alert=True).action_post()
        self.assertNotEqual(
            invoice_debit.journal_id, debit_journal,
            "La factura de origen debe quedar en el diario de venta normal, no en el dedicado de ND.",
        )

        with Form.from_action(self.env, invoice_debit.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2031-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))
        payment.action_post()
        self.env.cr.flush()

        note_debit = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(note_debit), 1)
        self.assertFalse(note_debit.l10n_ve_exchange_is_credit_note, "Este caso debía producir una ND.")
        self.assertEqual(
            note_debit.journal_id, debit_journal,
            "La Nota de Débito de diferencial debió usar el diario dedicado.",
        )
        self.assertTrue(
            note_debit.name.startswith("NDDIFT/2031/"),
            f"La ND debió numerarse con la secuencia dedicada y el año de su "
            f"propia fecha (2031). name={note_debit.name!r}",
        )

        # Rama de Nota de Crédito (tasa de la factura MAYOR que la del
        # pago -- mismas tasas que `test_exchange_difference_credit_note_branch`),
        # con el diario dedicado de ND ya configurado: no debe usarse aquí.
        self.usd.write({
            "active": True,
            "rate_ids": [
                Command.create({
                    "name": "2032-01-01",
                    "company_rate": 1 / 40.0,
                }),
                Command.create({
                    "name": "2032-08-01",
                    "company_rate": 1 / 36.0,
                }),
            ],
        })
        invoice_credit = self._create_invoice("2032-01-01")
        invoice_credit.with_context(move_action_post_alert=True).action_post()

        # `number_next_actual` de la secuencia de FACTURAS del diario,
        # capturado justo después de postear la factura (ya consumió su
        # propio correlativo) y antes de que exista la NC -- si
        # `_create_exchange_difference_note` numerara la NC con esta
        # MISMA secuencia en vez de `refund_sequence_id` (el bug
        # original), este valor avanzaría de nuevo al crear la NC.
        invoice_sequence = invoice_credit.journal_id.sequence_id
        invoice_sequence_next_before = invoice_sequence.number_next_actual

        with Form.from_action(self.env, invoice_credit.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2032-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))
        payment.action_post()
        self.env.cr.flush()

        note_credit = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
            ("id", "not in", note_debit.ids),
        ])
        self.assertEqual(len(note_credit), 1)
        self.assertTrue(note_credit.l10n_ve_exchange_is_credit_note, "Este caso debía producir una NC.")
        self.assertEqual(
            note_credit.journal_id, invoice_credit.journal_id,
            "La Nota de Crédito de diferencial debió usar el diario de venta de la factura de origen.",
        )
        self.assertNotEqual(
            note_credit.journal_id, debit_journal,
            "La Nota de Crédito de diferencial NO debió usar el diario dedicado de ND.",
        )
        self.assertTrue(
            note_credit.name.startswith("R"),
            f"La NC debió numerarse con la secuencia dedicada de refund "
            f"(prefijo 'R...', ver `od_journal_sequence._prepare_sequence`), "
            f"nunca con la secuencia de facturas. name={note_credit.name!r}",
        )
        self.assertNotEqual(
            note_credit.name, False,
            "La NC quedó sin numerar.",
        )
        invoice_sequence.invalidate_recordset(["number_next_actual"])
        self.assertEqual(
            invoice_sequence.number_next_actual, invoice_sequence_next_before,
            "Crear la NC de diferencial NO debió consumir un correlativo de "
            "la secuencia de FACTURAS del diario -- debe numerarse "
            "exclusivamente con `refund_sequence_id`.",
        )

    def test_regular_accountant_gets_user_error_not_access_error_on_missing_nc_sequence(self):
        """Regresión que ya NO prueba autoprovisión -- desde el fix de la
        revisión de código ("B5"), `_create_exchange_difference_note` NO
        autoprovisiona `refund_sequence_id` en silencio con `sudo()`
        sobre el diario de venta del cliente cuando falta: eso era un
        cambio PERMANENTE y silencioso en la numeración fiscal de un
        diario compartido con cualquier factura/NC de negocio normal,
        disparado dentro de `reconcile()` por quien sea que registre el
        pago. Ahora se exige configuración explícita de antemano, igual
        que ya exigía la rama de ND -- `raise UserError`.

        Lo que este test SIGUE necesitando probar (la razón original de
        `access_account_journal_manager` en juego, ver el comentario
        original de este test): que un contable SIN
        `group_account_manager` (`account.group_account_user`, "puede
        hacer todo salvo config avanzada") reciba ese `UserError` de
        NEGOCIO explícito -- nunca un `AccessError` crudo de permisos de
        `account.journal`, que revelaría detalle interno de seguridad en
        vez de decirle qué configurar."""
        accountant = self.env["res.users"].create({
            "name": "Contable Sin Permisos de Manager",
            "login": "contable.sin.manager@test.com",
            "email": "contable.sin.manager@test.com",
            "group_ids": [Command.set([
                self.env.ref("base.group_user").id,
                self.env.ref("account.group_account_user").id,
            ])],
            "company_id": self.company.id,
            "company_ids": [Command.set([self.company.id])],
        })

        # Diario de venta PROPIO de este test, deliberadamente SIN
        # `refund_sequence` -- el compartido `self.sale_journal` (usado
        # por casi todos los demás tests) ya la trae configurada desde
        # `setUpClass` (necesaria justo para NO tropezar con este mismo
        # `UserError` en los demás escenarios), así que ya no sirve para
        # reproducir la precondición "diario sin secuencia de NC" que
        # este test necesita.
        journal_without_nc_sequence = self.env["account.journal"].create({
            "name": "Ventas Sin Secuencia NC",
            "type": "sale",
            "code": "VNONC",
            "company_id": self.company.id,
        })

        # Tasas propias para estas fechas -- sin esto, `res.currency.rate`
        # cae a la última tasa configurada (`setUpClass`, 2026-08-01) para
        # AMBAS fechas (factura y pago), factura y pago quedan con la
        # MISMA tasa, no hay residual, y no se crea ninguna nota (con lo
        # que la aserción de más abajo nunca podría cumplirse, sin
        # importar si el fix de permisos funciona o no).
        self.usd.write({
            "active": True,
            "rate_ids": [
                Command.create({
                    "name": "2035-01-01",
                    "company_rate": 1 / 40.0,
                }),
                Command.create({
                    "name": "2035-08-01",
                    "company_rate": 1 / 36.0,
                }),
            ],
        })

        invoice = self._create_invoice("2035-01-01", journal=journal_without_nc_sequence)
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertFalse(
            invoice.journal_id.refund_sequence_id,
            "Precondición del escenario: el diario de venta NO debe tener "
            "una secuencia de refund configurada.",
        )

        accountant_env = self.env(
            user=accountant,
            context=dict(self.env.context, move_action_post_alert=True),
        )
        with Form.from_action(
            accountant_env,
            invoice.with_user(accountant).action_register_payment(),
        ) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2035-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        with self.assertRaises(UserError) as ctx:
            payment_wizard.with_user(accountant).action_create_payments()
        self.assertNotIsInstance(
            ctx.exception, AccessError,
            "Un contable sin `group_account_manager` debió recibir el "
            "UserError de negocio explícito (falta configurar la "
            "secuencia de NC del diario), nunca un AccessError crudo de "
            "permisos sobre `account.journal`.",
        )

        # Nada quedó a medio crear: ni la secuencia, ni una nota huérfana.
        invoice.invalidate_recordset()
        self.assertFalse(invoice.journal_id.refund_sequence_id)
        note = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
        ])
        self.assertFalse(note, "No debió crearse ninguna nota a medias tras el UserError.")

    def test_fallback_tags_generic_exchange_move_for_vendor_bill(self):
        """Cuando la línea que queda con residual NO pertenece a una
        factura de cliente (ej. una factura de PROVEEDOR), `reconcile()`
        no aplica su lógica de ND/NC -- cae directo al flujo nativo de
        Odoo (`_prepare_exchange_difference_move_vals`, fallback al
        principio del archivo), que sí genera su propio asiento genérico
        de diferencial cambiario (`move_type='entry'`). Ese asiento debe
        quedar igualmente etiquetado con `l10n_ve_exchange_diff_entry`."""
        supplier = self.env["res.partner"].create({"name": "Proveedor Prueba Reversal"})
        supplier.property_product_pricelist = False
        # `self.acc_payable`/`self.purchase_journal` -- creados con
        # fallback a nivel de clase (`setUpClass`), no una búsqueda
        # local sin respaldo: sin un diario de compras ya existente, el
        # `Form` de abajo revienta al INICIALIZARSE (antes de llegar a
        # asignar nada) con `UserError: No journal could be found ...
        # for any of those types: purchase`, calculado automáticamente
        # por Odoo (`_search_default_journal`) al abrir el Form.
        supplier.property_account_payable_id = self.acc_payable.id

        # `company.quick_edit_mode` -- sin esto, el campo `name` viene
        # invisible en el Form (`account.view_move_form`, núcleo de Odoo:
        # solo se muestra si ya tiene valor, si hay `name_placeholder`
        # calculado -esto último solo pasa si el diario de compras AÚN NO
        # tiene ninguna secuencia previa, cosa que no se cumple en una base
        # con datos reales-, o si `move.quick_edit_mode` es `True`). Ese
        # campo es COMPUTADO desde `company.quick_edit_mode` (no un simple
        # valor de contexto) -- hay que activarlo a nivel de compañía para
        # las facturas de proveedor.
        self.company.quick_edit_mode = "in_invoices"
        with Form(self.env["account.move"].with_context(default_move_type="in_invoice")) as bill_form:
            bill_form.partner_id = supplier
            bill_form.invoice_date = "2026-01-01"
            bill_form.journal_id = self.purchase_journal
            bill_form.currency_id = self.usd
            # Referencia del proveedor y correlativo fiscal -- ambos
            # requeridos para facturas de proveedor (a diferencia de las
            # de cliente, que los calculan solas con la secuencia del
            # diario).
            bill_form.name = "BILL-TEST-0001"
            bill_form.correlative = "00-00000001"
        bill = bill_form.save()
        with Form(bill) as bill_form_edit:
            with bill_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.sale_product
                line.quantity = 1
                line.price_unit = 100.0
        bill = bill_form_edit.save()
        bill.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, bill.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))
        self.env.cr.flush()

        bill.invalidate_recordset()
        self.assertEqual(bill.payment_state, "paid")

        # Ninguna ND/NC "de negocio" (documento fiscal `out_invoice`/
        # `out_refund`) nuestra debió crearse para esto.
        business_notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("partner_id", "=", supplier.id),
        ])
        self.assertFalse(business_notes)

        # El asiento genérico nativo de Odoo sí debió generarse, y quedar
        # etiquetado.
        generic_exchange_moves = self.env["account.move"].search([
            ("move_type", "=", "entry"),
            ("l10n_ve_exchange_diff_entry", "=", True),
        ])
        self.assertTrue(
            generic_exchange_moves,
            "Debió generarse (y etiquetarse) el asiento genérico nativo de diferencial.",
        )

        # El asiento genérico (move_type='entry', factura de PROVEEDOR)
        # nunca debe clasificar como ND/NC propia pese a tener
        # `l10n_ve_exchange_diff_entry=True` (ver
        # `_is_exchange_debit_note`/`_is_exchange_credit_note`,
        # `models/account_move.py`).
        generic_move = generic_exchange_moves[:1]
        self.assertFalse(generic_move._is_exchange_debit_note())
        self.assertFalse(generic_move._is_exchange_credit_note())

    def test_fallback_tags_generic_exchange_move_for_misc_entries(self):
        """`reconcile()` filtra por `move_type in ('out_invoice', 'out_refund')`
        ANTES de mirar `account_type` -- este caso prueba justo esa parte
        del filtro (no la de `account_type`, ya cubierta por
        `test_fallback_tags_generic_exchange_move_for_vendor_bill` con la
        cuenta por pagar): dos asientos contables MISCELÁNEOS
        (`move_type='entry'`, ni factura ni pago -- ej. un ajuste manual,
        o una reclasificación) que se concilian directamente sobre la
        MISMA cuenta por cobrar que usa el flujo de ND/NC, en moneda
        extranjera y con tasas de cambio distintas entre sí. Aun siendo
        `asset_receivable`, al no ser `out_invoice`/`out_refund` deben caer
        al flujo nativo de Odoo -- ninguna ND/NC de negocio, solo el
        asiento genérico nativo, etiquetado (mismo criterio que la NC/ND
        real, con el toggle de la compañía activo)."""
        partner = self.env["res.partner"].create({"name": "Cliente Prueba Asiento Misceláneo"})
        receivable = self.env["account.account"].search(
            [
                *self.env["account.account"]._check_company_domain(self.company),
                ("account_type", "=", "asset_receivable"),
            ],
            limit=1,
        )
        income = self.env["account.account"].search(
            [
                *self.env["account.account"]._check_company_domain(self.company),
                ("account_type", "=", "income"),
            ],
            limit=1,
        )

        # Reconocimiento inicial (equivalente a "la factura"): 100 USD a
        # una tasa de 40 VEF/USD -> 4000 VEF.
        entry_1 = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.sale_journal.id,
            "date": "2033-01-01",
            "line_ids": [
                (0, 0, {
                    "account_id": receivable.id,
                    "partner_id": partner.id,
                    "currency_id": self.usd.id,
                    "amount_currency": 100.0,
                    "debit": 4000.0,
                    "credit": 0.0,
                }),
                (0, 0, {
                    "account_id": income.id,
                    "partner_id": partner.id,
                    "debit": 0.0,
                    "credit": 4000.0,
                }),
            ],
        })
        entry_1.action_post()

        # Liquidación (equivalente a "el pago"): mismos 100 USD, pero a una
        # tasa de 36 VEF/USD -> 3600 VEF -- deja un residual de 400 VEF,
        # el mismo tipo de diferencial que dispara la ND/NC real.
        entry_2 = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.sale_journal.id,
            "date": "2033-08-01",
            "line_ids": [
                (0, 0, {
                    "account_id": receivable.id,
                    "partner_id": partner.id,
                    "currency_id": self.usd.id,
                    "amount_currency": -100.0,
                    "debit": 0.0,
                    "credit": 3600.0,
                }),
                (0, 0, {
                    "account_id": income.id,
                    "partner_id": partner.id,
                    "debit": 3600.0,
                    "credit": 0.0,
                }),
            ],
        })
        entry_2.action_post()

        receivable_lines = (entry_1 + entry_2).line_ids.filtered(
            lambda l: l.account_id == receivable
        )
        receivable_lines.reconcile()
        self.env.cr.flush()

        receivable_lines.invalidate_recordset()
        self.assertTrue(
            all(receivable_lines.mapped("reconciled")),
            "Las líneas de la cuenta por cobrar debieron quedar conciliadas entre sí.",
        )

        # Ninguna ND/NC "de negocio" nuestra debió crearse para este
        # partner -- ni siquiera un `out_invoice`/`out_refund` en borrador.
        business_notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("partner_id", "=", partner.id),
        ])
        self.assertFalse(
            business_notes,
            "No debió crearse ninguna ND/NC de negocio para una conciliación de asientos misceláneos.",
        )

        # El asiento genérico nativo de Odoo sí debió generarse (con el
        # toggle de la compañía activo) y quedar etiquetado, exactamente
        # igual que en el caso de la factura de proveedor.
        generic_exchange_moves = self.env["account.move"].search([
            ("move_type", "=", "entry"),
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("id", "not in", (entry_1 + entry_2).ids),
        ])
        self.assertTrue(
            generic_exchange_moves,
            "Debió generarse (y etiquetarse) el asiento genérico nativo de diferencial "
            "aun tratándose de la cuenta por cobrar, porque el origen no es "
            "out_invoice/out_refund.",
        )

        # El asiento genérico (move_type='entry') NUNCA debe clasificar
        # como ND/NC propia -- `l10n_ve_exchange_diff_entry=True` por sí
        # solo no alcanza, `_is_exchange_debit_note()`/`_is_exchange_credit_note()`
        # también exigen `move_type` de factura/nota de cliente (ver
        # `models/account_move.py`). Si esto fallara, `_compute_name_by_sequence`
        # intentaría numerar este asiento genérico con la secuencia
        # dedicada de ND, y `_reverse_moves` le ensuciaría
        # `l10n_ve_exchange_original_id` como si fuera la reversión de una
        # ND real.
        generic_move = generic_exchange_moves[:1]
        self.assertFalse(
            generic_move._is_exchange_debit_note(),
            "El asiento genérico de diferencial NUNCA debe clasificar como ND propia.",
        )
        self.assertFalse(
            generic_move._is_exchange_credit_note(),
            "El asiento genérico de diferencial NUNCA debe clasificar como NC propia.",
        )

    def test_second_partial_payment_gets_its_own_note(self):
        """Una factura pagada en DOS cuotas (dos conciliaciones separadas,
        en fechas/tasas distintas -- primera con GANANCIA, segunda con
        PÉRDIDA) debe acumular una ND/NC de diferencial POR CADA cuota --
        el guard `existing_note` de `_create_exchange_difference_note` es
        por (factura, pago), no solo por factura, así que el diferencial
        del segundo pago parcial no debe perderse (antes de este fix, la
        existencia de la nota del primer pago bloqueaba silenciosamente
        la del segundo).

        Montos deterministas: la ND del primer pago es 50 USD × |40-44| =
        200 Bs (ganancia). El monto de la NC del segundo pago es 50 USD ×
        |40-30| = 500 Bs (pérdida) -- Odoo calcula el residual de CADA
        porción de la factura siempre contra su tasa ORIGINAL de
        contabilización (40, la de la factura), nunca contra la tasa de un
        pago parcial anterior: el primer pago (50 USD a 44) liquida su
        propia mitad de forma independiente y no altera la base de cálculo
        de la segunda mitad, que sigue anclada a 40. Es el propio motor de
        conciliación de Odoo (``_prepare_exchange_difference_move_vals``)
        quien determina este monto -- este módulo solo intercepta ese
        cálculo ya hecho y lo redirige a la NC en vez de al asiento
        genérico."""
        self.usd.write({
            "active": True,
            "rate_ids": [
                Command.create({"name": "2026-05-01", "company_rate": 1 / 44.0}),
                Command.create({"name": "2026-09-01", "company_rate": 1 / 30.0}),
            ],
        })

        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        # Primer pago parcial (50 USD), tasa MAYOR que la de la factura
        # (44 > 40) -> ganancia -> Nota de Débito. Al ser una ND, se
        # concilia contra el remanente del PAGO (nunca contra la propia
        # factura), así que no interfiere con el segundo pago.
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-05-01"
            pay_form.save()
            pay_form.amount = 50.0
            pay_form.save()
        payment1_wizard = pay_form.record
        action1 = payment1_wizard.action_create_payments()
        payment1 = self.env["account.payment"].browse(action1.get("res_id"))

        self.env.cr.flush()
        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()
        self.assertEqual(invoice.payment_state, "partial", "Debía quedar pendiente el segundo 50%.")

        note1 = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
        ])
        self.assertEqual(len(note1), 1, "El primer pago parcial debió generar su propia ND/NC.")
        self.assertEqual(note1.move_type, "out_invoice", "Con tasa mayor que la de la factura, se esperaba ND.")
        self.assertEqual(note1.amount_total, 200.0)
        self.assertEqual(note1.invoice_line_ids.price_unit, 200.0)
        self.assertEqual(
            note1.invoice_line_ids.account_id, self.company.income_currency_exchange_account_id,
        )
        self.assertEqual(note1.date, fields.Date.from_string("2026-05-01"))
        self.assertEqual(note1.l10n_ve_exchange_payment_id, payment1.move_id)

        # Segundo pago parcial (los 50 USD restantes), tasa MENOR que la
        # que quedó implícita en el residual contable de la factura tras
        # el primer pago -> pérdida -> Nota de Crédito, conciliada contra
        # el remanente de la propia factura.
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-09-01"
            pay_form.save()
            pay_form.amount = 50.0
            pay_form.save()
        payment2_wizard = pay_form.record
        action2 = payment2_wizard.action_create_payments()
        payment2 = self.env["account.payment"].browse(action2.get("res_id"))

        self.env.cr.flush()
        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
        ])
        self.assertEqual(
            len(notes), 2,
            "Cada pago parcial debió generar su propia ND/NC -- el diferencial del "
            "segundo pago no debe perderse por la existencia de la nota del primero.",
        )
        note2 = notes - note1
        self.assertEqual(note2.move_type, "out_refund", "Se esperaba NC (residual real en débito tras el 2º pago).")
        self.assertEqual(note2.amount_total, 500.0)
        self.assertEqual(note2.invoice_line_ids.price_unit, 500.0)
        self.assertEqual(
            note2.invoice_line_ids.account_id, self.company.expense_currency_exchange_account_id,
        )
        self.assertEqual(note2.date, fields.Date.from_string("2026-09-01"))
        self.assertEqual(note2.l10n_ve_exchange_payment_id, payment2.move_id)

        self.assertEqual(
            set(notes.mapped("l10n_ve_exchange_payment_id").ids),
            {payment1.move_id.id, payment2.move_id.id},
            "Cada nota debe quedar vinculada a SU PROPIO pago.",
        )

        # La NC (pérdida) SIEMPRE representa un monto que la factura
        # todavía tiene abierto -- debe quedar cerrada por su propia
        # conciliación, sin excepción.
        note2_line = note2.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note2_line.reconciled, "La NC debió quedar cerrada por su propia conciliación.")

        # La ND (ganancia) del primer pago parcial también queda cerrada
        # de inmediato: se concilia contra la propia línea del PAGO que
        # originó el diferencial (`reconciled_lines_ids` sobre esa
        # línea), no contra la factura -- así que no depende de que
        # quede un sobrante disponible en la factura.
        note1_line = note1.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note1_line.reconciled, "La ND debió quedar cerrada por su propia conciliación.")

    def test_grouped_payment_documents_exchange_difference_for_every_invoice(self):
        """Un único pago aplicado a VARIAS facturas de cliente a la vez
        (``group_payment`` en el wizard `account.payment.register`) debía
        antes documentar el diferencial SOLO de la primera factura
        (`invoice_lines[:1]`) -- ahora `reconcile()` itera cada línea de
        factura por separado, así que cada una debe recibir su propia
        ND/NC."""
        invoice_1 = self._create_invoice("2026-01-01")
        invoice_1.with_context(move_action_post_alert=True).action_post()
        invoice_2 = self._create_invoice("2026-01-01")
        invoice_2.with_context(move_action_post_alert=True).action_post()
        invoices = invoice_1 | invoice_2

        lines_to_pay = invoices.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        action = lines_to_pay.action_register_payment()
        ctx = dict(action["context"], active_model="account.move.line", active_ids=lines_to_pay.ids)
        with Form(self.env["account.payment.register"].with_context(ctx)) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.group_payment = True
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()
        invoice_1.invalidate_recordset()
        invoice_2.invalidate_recordset()

        self.assertEqual(invoice_1.payment_state, "paid")
        self.assertEqual(invoice_2.payment_state, "paid")

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_payment_id", "=", payment.move_id.id),
        ])
        self.assertEqual(
            len(notes), 2,
            "El pago agrupado debió generar una ND/NC por cada factura involucrada, "
            "no solo la primera.",
        )
        self.assertEqual(
            set(notes.mapped("l10n_ve_exchange_invoice_id").ids),
            {invoice_1.id, invoice_2.id},
            "Cada factura del pago agrupado debe tener su propia ND/NC.",
        )
        # Cada nota tiene el monto correcto (100 USD x |40-36| = 400 Bs) y
        # queda cerrada de inmediato por su propia conciliación
        # (`reconciled_lines_ids`, ver `_create_exchange_difference_note`)
        # -- sin excepción, aun en un pago agrupado.
        for note in notes:
            self.assertEqual(note.amount_total, 400.0)
            note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
            self.assertTrue(note_line.reconciled, "Cada nota del pago agrupado debió quedar cerrada.")
            self.assertTrue(self.company.currency_id.is_zero(note_line.amount_residual))

    def test_grouped_payment_gain_direction_invoice_attribution_is_exact(self):
        """Un pago AGRUPADO que liquida DOS facturas de montos DISTINTOS
        (100 y 500 USD) a la vez, en dirección de GANANCIA (Odoo suele
        atribuir el residual al lado del PAGO, no de la factura, en esa
        dirección -- a diferencia de
        `test_grouped_payment_documents_exchange_difference_for_every_invoice`,
        que usa dirección de pérdida y por eso no dispara este caso).

        Monto distinto por factura a propósito: con dos facturas
        IDÉNTICAS, cualquier atribución (correcta o no) produce el mismo
        resultado observable y no distingue un swap -- este test
        confirma que cada nota queda vinculada a la factura que
        REALMENTE originó su residual (400 Bs -> factura de 100 USD,
        2000 Bs -> factura de 500 USD), no una adivinanza por orden.

        Antes de dos fixes distintos, este caso falló de dos formas
        reales, ambas confirmadas ejecutando este mismo test contra
        cada versión:
        1. Atribuir siempre "la primera factura" a cualquier residual del
           lado del pago colisionaba dos residuales DISTINTOS contra el
           mismo par (factura, pago) -- el guard de duplicados
           descartaba el segundo como repetido, PERDIENDO un diferencial
           real (solo se creaba 1 nota en vez de 2).
        2. Repartir esos residuales EN ORDEN (round-robin) entre las
           facturas candidatas evitaba la pérdida, pero podía
           intercambiar a cuál factura se vincula cada nota cuando sus
           montos difieren (confirmado con un swap real: la nota de 2000
           Bs quedaba vinculada a la factura de 100 en vez de la de 500).

        El fix final (`_prepare_reconciliation_single_partial` sobrescrito
        para capturar la pareja REAL de cada partial antes de que Odoo
        calcule el residual) elimina la adivinanza por completo: se
        deriva la factura exacta de la propia conciliación, nunca del
        orden de aparición."""
        self.usd.write({
            "active": True,
            "rate_ids": [
                Command.create({"name": "2035-01-01", "company_rate": 1 / 36.0}),
                Command.create({"name": "2035-08-01", "company_rate": 1 / 40.0}),
            ],
        })

        invoice_1 = self._create_invoice("2035-01-01")
        invoice_1.with_context(move_action_post_alert=True).action_post()
        invoice_2 = self._create_invoice("2035-01-01")
        with Form(invoice_2) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.edit(0) as line:
                line.price_unit = 500.0
        invoice_2 = inv_form_edit.save()
        invoice_2.with_context(move_action_post_alert=True).action_post()
        invoices = invoice_1 | invoice_2

        lines_to_pay = invoices.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        action = lines_to_pay.action_register_payment()
        ctx = dict(action["context"], active_model="account.move.line", active_ids=lines_to_pay.ids)
        with Form(self.env["account.payment.register"].with_context(ctx)) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2035-08-01"
            pay_form.group_payment = True
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()
        invoice_1.invalidate_recordset()
        invoice_2.invalidate_recordset()

        self.assertEqual(invoice_1.payment_state, "paid")
        self.assertEqual(invoice_2.payment_state, "paid")

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("l10n_ve_exchange_payment_id", "=", payment.move_id.id),
        ])

        # Innegociable: nunca cae al asiento genérico -- se crean las DOS
        # notas, una por factura, cada una cerrada contra el pago.
        self.assertEqual(
            len(notes), 2,
            "El pago agrupado en dirección de ganancia debió generar una ND/NC por "
            "cada factura, cruzada contra el pago -- nunca caer al asiento nativo.",
        )
        self.assertEqual(
            set(notes.mapped("l10n_ve_exchange_invoice_id").ids), {invoice_1.id, invoice_2.id},
            "Cada nota debe quedar vinculada a una factura distinta, sin colisionar "
            "ambas sobre la misma.",
        )

        # Atribución EXACTA, no una adivinanza: la nota de la factura de
        # 100 USD es 100 × (40 - 36) = 400 Bs; la de la factura de 500
        # USD es 500 × (40 - 36) = 2000 Bs -- si el fix adivinara por
        # orden en vez de derivar la pareja real del partial, estos dos
        # montos podrían aparecer intercambiados entre las facturas.
        note_1 = notes.filtered(lambda n: n.l10n_ve_exchange_invoice_id == invoice_1)
        note_2 = notes.filtered(lambda n: n.l10n_ve_exchange_invoice_id == invoice_2)
        self.assertEqual(note_1.amount_total, 400.0, "La nota de la factura de 100 USD debió ser de 400 Bs.")
        self.assertEqual(note_2.amount_total, 2000.0, "La nota de la factura de 500 USD debió ser de 2000 Bs.")
        self.assertEqual(sum(notes.mapped("amount_total")), 2400.0)

        for note in notes:
            note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
            self.assertTrue(note_line.reconciled, "Cada nota debió quedar cerrada, sin excepción.")
            self.assertTrue(self.company.currency_id.is_zero(note_line.amount_residual))
            self.assertEqual(note.l10n_ve_exchange_payment_id, payment.move_id)

    def test_invoice_settled_against_unrelated_credit_note_still_generates_note(self):
        """DIAGNÓSTICO -- ver qué produce hoy `reconcile()` cuando una
        factura se salda contra una NC de cliente SUELTA (no un pago
        bancario): el filtro `invoice_lines` de `reconcile()` clasifica
        AMBAS líneas (factura Y NC) como "línea de factura de cliente"
        (ambas `asset_receivable`, `move_type in ('out_invoice',
        'out_refund')`) -- dejando `payment_lines` VACÍO. Este test fija
        el comportamiento observado, sea cual sea, para que quede
        documentado y protegido contra regresión."""
        with Form(self.env["account.move"].with_context(default_move_type="out_refund")) as cn_form:
            cn_form.partner_id = self.partner
            cn_form.invoice_date = "2026-08-01"
            cn_form.journal_id = self.sale_journal
            cn_form.currency_id = self.usd
        credit_note = cn_form.save()
        with Form(credit_note) as cn_form_edit:
            with cn_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.sale_product
                line.quantity = 1
                line.price_unit = 100.0
        credit_note = cn_form_edit.save()
        self.assertFalse(credit_note.reversed_entry_id)
        self.assertFalse(credit_note.debit_origin_id)
        credit_note.with_context(move_action_post_alert=True).action_post()

        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        cn_line = credit_note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        # Widget "outstanding credits" de la factura -- el mismo camino
        # real que usa un usuario para saldar una factura contra una NC
        # suelta del mismo cliente, sin pasar por ningún pago bancario.
        invoice.js_assign_outstanding_line(cn_line.id)
        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()
        credit_note.invalidate_recordset()
        cn_line.invalidate_recordset()

        self.assertTrue(inv_line.reconciled, "La factura y la NC debieron quedar conciliadas entre sí.")
        self.assertTrue(cn_line.reconciled)

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("id", "not in", (invoice + credit_note).ids),
        ])
        self.assertEqual(
            len(notes), 1,
            "La conciliación factura<->NC (tasas de 2026-01-01 y 2026-08-01, "
            "distintas) debió producir un residual de diferencial cambiario "
            "real -- y, tras el fix de atribución de pago (B6, "
            "`_prepare_exchange_difference_move_vals`), ese residual ya no "
            "se pierde por `payment_lines` vacío: se genera igual una "
            "ND/NC de diferencial, atribuida a quien de las dos líneas "
            "haya quedado con el residual real.",
        )
        note = notes
        # Cualquiera de las dos líneas (factura o NC) pudo terminar con
        # el residual según a cuál se lo atribuya el motor nativo de
        # Odoo -- lo único que importa es que la nota quede vinculada a
        # UNA de las dos, nunca huérfana ni sin `l10n_ve_exchange_invoice_id`.
        self.assertIn(note.l10n_ve_exchange_invoice_id, invoice + credit_note)
        self.assertTrue(note.l10n_ve_exchange_payment_id, "La nota no debió quedar sin contraparte de pago.")
        self.assertIn(note.l10n_ve_exchange_payment_id, invoice + credit_note)
        self.assertNotEqual(
            note.l10n_ve_exchange_invoice_id, note.l10n_ve_exchange_payment_id,
            "La nota nunca debió atribuirse a sí misma como su propio pago.",
        )
        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled, "La ND/NC debió quedar cerrada por su propia conciliación.")

    def test_standalone_credit_note_settled_with_exchange_difference_generates_own_note(self):
        """Una Nota de Crédito de cliente GENUINA -- `out_refund` creada
        directo (ej. devolución de mercancía), sin `reversed_entry_id` ni
        `debit_origin_id`, o sea NO derivada de ninguna factura ni de este
        módulo -- en moneda extranjera, reembolsada al cliente en una
        fecha con tasa distinta, debe generar su PROPIA ND/NC de
        diferencial, igual que una factura: el filtro de `reconcile()`
        acepta `move_type in ('out_invoice', 'out_refund')` de forma
        genérica, no solo facturas."""
        with Form(self.env["account.move"].with_context(default_move_type="out_refund")) as cn_form:
            cn_form.partner_id = self.partner
            cn_form.invoice_date = "2026-01-01"
            cn_form.journal_id = self.sale_journal
            cn_form.currency_id = self.usd
        credit_note = cn_form.save()
        with Form(credit_note) as cn_form_edit:
            with cn_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.sale_product
                line.quantity = 1
                line.price_unit = 100.0
        credit_note = cn_form_edit.save()
        self.assertFalse(credit_note.reversed_entry_id)
        self.assertFalse(credit_note.debit_origin_id)
        credit_note.with_context(move_action_post_alert=True).action_post()
        cn_line = credit_note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, credit_note.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()
        credit_note.invalidate_recordset()
        cn_line.invalidate_recordset()

        self.assertEqual(credit_note.payment_state, "paid")
        self.assertTrue(cn_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(cn_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", credit_note.id),
        ])
        self.assertEqual(
            len(notes), 1,
            "Una Nota de Crédito de cliente genuina en moneda extranjera también debió "
            "generar su propia ND/NC de diferencial al liquidarse con tasa distinta.",
        )
        note_line = notes.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled, "La ND/NC debió quedar cerrada por su propia conciliación.")

        # Mismas tasas del `setUpClass` -- rama ND (ganancia), monto
        # determinista: 100 USD × (40 - 36) = 400.0 Bs.
        self.assertEqual(notes.move_type, "out_invoice")
        self.assertEqual(notes.debit_origin_id, credit_note)
        self.assertEqual(notes.amount_total, 400.0)
        self.assertEqual(notes.invoice_line_ids.price_unit, 400.0)
        self.assertEqual(notes.invoice_line_ids.account_id, self.company.income_currency_exchange_account_id)

    def test_business_credit_note_of_invoice_excluded_from_own_logic(self):
        """Una Nota de Crédito de NEGOCIO real (emitida vía el asistente
        nativo `account.move.reversal` -- ej. devolución sobre una
        factura ya pagada, NADA que ver con este módulo) tiene
        `reversed_entry_id` apuntando a la factura que revierte -- el
        guard `not l.move_id.reversed_entry_id` de `reconcile()` la
        excluye de nuestra lógica: al liquidarla con tasa distinta, debe
        caer al asiento GENÉRICO nativo de Odoo, nunca a una ND/NC
        propia (que quedaría vinculada, incorrectamente, a la factura
        original vía `l10n_ve_exchange_invoice_id`)."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()

        # La factura de origen se salda PRIMERO, a la MISMA tasa (sin
        # diferencial) -- si quedara abierta, Odoo reconciliaría la NC de
        # negocio automáticamente contra ella al postearla (comportamiento
        # nativo: busca crédito disponible del mismo partner), sin dejar
        # residual para registrar un reembolso aparte.
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-01-01"
            pay_form.save()
        payment_wizard = pay_form.record
        payment_wizard.action_create_payments()
        self.env.cr.flush()
        invoice.invalidate_recordset()
        self.assertEqual(invoice.payment_state, "paid")

        reversal_wizard = self.env["account.move.reversal"].with_context(
            active_model="account.move", active_ids=invoice.ids,
        ).create({
            "reason": "Devolución de prueba",
            "journal_id": invoice.journal_id.id,
        })
        action = reversal_wizard.reverse_moves()
        business_credit_note = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(business_credit_note.reversed_entry_id, invoice)
        if business_credit_note.state != "posted":
            business_credit_note.with_context(move_action_post_alert=True).action_post()
        business_credit_note.invalidate_recordset()
        self.assertEqual(
            business_credit_note.payment_state, "not_paid",
            "La NC de negocio no debía tener nada más contra qué auto-conciliarse.",
        )
        cn_line = business_credit_note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        # Reembolso al cliente (la NC de negocio queda a favor del
        # cliente) en una fecha con tasa distinta a la de la factura.
        with Form.from_action(self.env, business_credit_note.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()
        business_credit_note.invalidate_recordset()
        cn_line.invalidate_recordset()

        self.assertTrue(cn_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(cn_line.amount_residual))

        business_notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
        ])
        self.assertFalse(
            business_notes,
            "La NC de negocio (reversión real de la factura) no debió generar una "
            "ND/NC propia de diferencial vinculada a la factura original.",
        )

        generic_exchange_moves = self.env["account.move"].search([
            ("move_type", "=", "entry"),
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("id", "not in", (invoice + business_credit_note).ids),
        ])
        self.assertTrue(
            generic_exchange_moves,
            "Debió generarse el asiento genérico nativo de diferencial para la NC de negocio.",
        )

    def test_business_debit_note_of_invoice_excluded_from_own_logic(self):
        """Una Nota de Débito de NEGOCIO real -- `out_invoice` con
        `debit_origin_id` apuntando a otra factura (ej. un cargo
        adicional sobre una factura ya emitida, simulado aquí escribiendo
        el campo directamente ya que el núcleo de Odoo 19 no trae un
        asistente `account.debit.note` genérico) -- el guard
        `not l.move_id.debit_origin_id` de `reconcile()` la excluye de
        nuestra lógica: al liquidarla con tasa distinta, debe caer al
        asiento GENÉRICO nativo, nunca a una ND/NC propia."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()

        business_debit_note = self._create_invoice("2026-01-01")
        business_debit_note.debit_origin_id = invoice.id
        business_debit_note.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(business_debit_note.debit_origin_id, invoice)
        dn_line = business_debit_note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, business_debit_note.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()
        business_debit_note.invalidate_recordset()
        dn_line.invalidate_recordset()

        self.assertEqual(business_debit_note.payment_state, "paid")
        self.assertTrue(dn_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(dn_line.amount_residual))

        business_notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("l10n_ve_exchange_invoice_id", "=", business_debit_note.id),
        ])
        self.assertFalse(
            business_notes,
            "La ND de negocio (con debit_origin_id propio) no debió generar una "
            "ND/NC propia de diferencial.",
        )

        generic_exchange_moves = self.env["account.move"].search([
            ("move_type", "=", "entry"),
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("id", "not in", (invoice + business_debit_note).ids),
        ])
        self.assertTrue(
            generic_exchange_moves,
            "Debió generarse el asiento genérico nativo de diferencial para la ND de negocio.",
        )

    def test_igtf_note_debit_origin_invoice_excluded_from_own_logic(self):
        """Una factura marcada con `l10n_ve_igtf_note_debit_origin` (flag
        del módulo `l10n_ve_igtf_note_debit` -- Nota de Débito automática
        de percepción de IGTF; puede no estar instalado en este entorno de
        pruebas, de ahí el `getattr` con default `False` en el guard de
        `reconcile()`) debe excluirse de nuestra lógica igual que
        `debit_origin_id`/`reversed_entry_id` -- se simula escribiendo el
        campo directamente si existe en el modelo; si el módulo no está
        instalado, el test se salta (nada que ejercitar)."""
        if "l10n_ve_igtf_note_debit_origin" not in self.env["account.move"]._fields:
            self.skipTest("l10n_ve_igtf_note_debit no está instalado en este entorno de pruebas.")

        invoice = self._create_invoice("2026-01-01")
        invoice.l10n_ve_igtf_note_debit_origin = True
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()
        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        business_notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
        ])
        self.assertFalse(
            business_notes,
            "Una factura de percepción de IGTF (l10n_ve_igtf_note_debit_origin) no "
            "debió generar una ND/NC propia de diferencial.",
        )

    def test_reverse_exchange_note_on_draft_note_unlinks_it(self):
        """`_reverse_exchange_note` sobre una nota en borrador (nunca
        llegó a postearse -- por ejemplo, quedó a medias por cualquier
        motivo antes de este punto) la BORRA directamente en vez de
        intentar revertirla -- no hay ningún documento fiscal real (sin
        correlativo posteado) que preservar."""
        draft_note = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "l10n_ve_exchange_diff_entry": True,
        })
        self.assertEqual(draft_note.state, "draft")
        note_id = draft_note.id

        draft_note._reverse_exchange_note()

        self.assertFalse(
            self.env["account.move"].search([("id", "=", note_id)]),
            "Una nota en borrador debió BORRARSE al revertirla, no dejarse a medias.",
        )

    def test_reverse_exchange_note_noop_when_cancelled(self):
        """`_reverse_exchange_note` sobre una nota que NO está ni en
        borrador ni posteada (ej. cancelada por cualquier otra vía) no
        hace nada -- ni la revierte, ni lanza error. Solo se revierten
        notas efectivamente posteadas (documento fiscal real)."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))
        self.env.cr.flush()

        note = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
        ])
        self.assertEqual(len(note), 1)
        self.assertEqual(note.state, "posted")

        # Se fuerza directo por SQL a un estado que `_reverse_exchange_note`
        # no maneja (ni 'draft' ni 'posted') -- se salta el ORM a propósito
        # para simular ese estado sin pasar por el flujo real de cancelación
        # (que de por sí ya rompería la conciliación y la revertiría antes).
        self.env.cr.execute(
            "UPDATE account_move SET state = 'cancel' WHERE id = %s", (note.id,),
        )
        note.invalidate_recordset()
        self.assertEqual(note.state, "cancel")

        # No debe lanzar ni crear ninguna reversión.
        note._reverse_exchange_note()

        reversals = self.env["account.move"].search([("reversed_entry_id", "=", note.id)])
        self.assertFalse(reversals, "Una nota que no está 'posted' no debe generar ninguna reversión.")

    def test_compute_name_by_sequence_skips_already_named_note(self):
        """`_compute_name_by_sequence` no debe re-numerar una ND/NC que ya
        tiene un nombre real asignado (`move.name and move.name != '/'`) --
        se ejercita llamando el método una SEGUNDA vez sobre una nota ya
        posteada y numerada; el nombre no debe cambiar."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))
        self.env.cr.flush()

        note = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
        ])
        self.assertEqual(len(note), 1)
        original_name = note.name
        self.assertTrue(original_name and original_name != "/")

        note._compute_name_by_sequence()

        self.assertEqual(
            note.name, original_name,
            "Una nota ya numerada no debe recibir un nuevo número al recomputar el nombre.",
        )

    def test_sequence_matches_date_true_for_exchange_entries(self):
        """`_sequence_matches_date` siempre retorna `True` para una ND/NC
        propia (o su reversión) -- su secuencia es independiente del
        diario, comparar contra la fecha de la secuencia nativa no aplica
        (a diferencia de una factura/nota normal, donde Odoo sí valida
        esa consistencia)."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))
        self.env.cr.flush()

        note = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
        ])
        self.assertEqual(len(note), 1)
        self.assertTrue(note.l10n_ve_exchange_diff_entry)

        self.assertTrue(
            note._sequence_matches_date(),
            "Una ND/NC de diferencial cambiario debe reportar su secuencia como "
            "consistente con la fecha, sin importar la fecha real del diario.",
        )

    def test_breaking_partial_without_invoice_side_does_not_search_for_note(self):
        """`js_remove_outstanding_partial` solo busca una nota que revertir
        cuando alguno de los dos movimientos de la conciliación rota es
        `out_invoice`/`out_refund` (`invoice` no vacío) -- se ejercita el
        caso contrario (dos asientos MISCELÁNEOS, `move_type='entry'`,
        igual que en `test_fallback_tags_generic_exchange_move_for_misc_entries`)
        rompiendo su conciliación: debe desconciliarse con normalidad, sin
        buscar ni intentar revertir ninguna nota."""
        partner = self.env["res.partner"].create({"name": "Cliente Prueba Ruptura Misc"})
        receivable = self.env["account.account"].search(
            [*self.env["account.account"]._check_company_domain(self.company), ("account_type", "=", "asset_receivable")],
            limit=1,
        )
        income = self.env["account.account"].search(
            [*self.env["account.account"]._check_company_domain(self.company), ("account_type", "=", "income")],
            limit=1,
        )

        entry_1 = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.sale_journal.id,
            "date": "2033-01-01",
            "line_ids": [
                (0, 0, {
                    "account_id": receivable.id, "partner_id": partner.id,
                    "currency_id": self.usd.id, "amount_currency": 100.0,
                    "debit": 4000.0, "credit": 0.0,
                }),
                (0, 0, {"account_id": income.id, "partner_id": partner.id, "debit": 0.0, "credit": 4000.0}),
            ],
        })
        entry_1.action_post()

        entry_2 = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.sale_journal.id,
            "date": "2033-08-01",
            "line_ids": [
                (0, 0, {
                    "account_id": receivable.id, "partner_id": partner.id,
                    "currency_id": self.usd.id, "amount_currency": -100.0,
                    "debit": 0.0, "credit": 3600.0,
                }),
                (0, 0, {"account_id": income.id, "partner_id": partner.id, "debit": 3600.0, "credit": 0.0}),
            ],
        })
        entry_2.action_post()

        receivable_lines = (entry_1 + entry_2).line_ids.filtered(lambda l: l.account_id == receivable)
        receivable_lines.reconcile()
        self.env.cr.flush()
        receivable_lines.invalidate_recordset()
        self.assertTrue(all(receivable_lines.mapped("reconciled")))

        partial = receivable_lines[0].matched_debit_ids or receivable_lines[0].matched_credit_ids
        self.assertTrue(partial, "Debía existir un partial entre los dos asientos misceláneos.")

        # No debe lanzar ningún error (ninguna nota de negocio involucrada)
        # y debe desconciliar con normalidad.
        entry_1.js_remove_outstanding_partial(partial[:1].id)
        self.env.cr.flush()
        receivable_lines.invalidate_recordset()
        self.assertFalse(
            any(receivable_lines.mapped("reconciled")),
            "Los asientos misceláneos debieron quedar desconciliados tras romper el partial.",
        )

    def test_breaking_reconciliation_without_generated_note_is_noop(self):
        """`js_remove_outstanding_partial` busca una nota por (factura,
        pago) solo cuando ambos existen -- si esa búsqueda no encuentra
        ninguna (porque nunca se generó, ej. factura y pago EXACTAMENTE a
        la misma tasa y fecha, sin residual de diferencial alguno), no
        debe lanzar error: simplemente no hay nada que revertir."""
        same_day_invoice = self._create_invoice("2026-01-01")
        same_day_invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = same_day_invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, same_day_invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            # Mismo día Y misma tasa que la factura -- sin residual de
            # diferencial cambiario posible.
            pay_form.payment_date = "2026-01-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))
        self.env.cr.flush()

        same_day_invoice.invalidate_recordset()
        inv_line.invalidate_recordset()
        self.assertTrue(inv_line.reconciled)

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", same_day_invoice.id),
        ])
        self.assertFalse(notes, "Sin diferencial real, no debió generarse ninguna ND/NC.")

        partial = (inv_line.matched_debit_ids | inv_line.matched_credit_ids).filtered(
            lambda p: same_day_invoice in (p.debit_move_id.move_id, p.credit_move_id.move_id)
        )
        self.assertTrue(partial)

        # No debe lanzar error aunque no exista ninguna nota que buscar.
        same_day_invoice.js_remove_outstanding_partial(partial[:1].id)
        self.env.cr.flush()
        inv_line.invalidate_recordset()
        self.assertFalse(inv_line.reconciled, "La factura debió quedar desconciliada con normalidad.")
