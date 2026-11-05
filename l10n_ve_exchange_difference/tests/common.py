from odoo import Command
from odoo.tests import Form
from odoo.tests.common import TransactionCase


class ExchangeNoteCommon(TransactionCase):
    """Fixture compartido de los tests de diferencial cambiario (sin tests
    propios): compañía en VEF con USD como moneda alterna, tasas 40 (2026-01-01)
    y 36 (2026-08-01) para USD, diarios de venta/ND/banco (VEF y USD), producto
    y lista de precios de la nota, y los helpers para crear facturas."""

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

        # `_check_l10n_ve_exchange_use_nd_nc_requires_config` (res_company.py)
        # defiere su chequeo final a `cr.precommit` -- necesario para no dar
        # un falso positivo mientras el toggle y el producto/pricelist se
        # escriben en llamadas `write()` separadas (ver su propio docstring).
        # Ese callback pendiente solo se descarga cuando algo llama
        # `cr.flush()` (p.ej. `self.assertRaises` -- SÍ sobreescrito por Odoo
        # para hacer flush; `assertRaisesRegex` NO). Sin este flush explícito
        # acá, el callback queda dormido en `cr.precommit` durante TODA la
        # clase -- hasta el primer test que use `assertRaises` plano, que
        # puede ya haber corrompido a propósito el estado de la compañía por
        # SQL directo (ej. `test_missing_note_pricelist_raises_user_error_defense_in_depth`)
        # para ejercitar el guard en tiempo de conciliación. El chequeo
        # dormido entonces lee ESE estado ajeno y revienta con
        # `ValidationError` antes de que el bloque bajo prueba de ESE test
        # siquiera se ejecute, enmascarando el `UserError` esperado.
        cls.env.cr.flush()

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
                ("inbound_payment_method_line_ids.payment_account_id", "!=", False),
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
