import random

from odoo import Command
from odoo.tests import Form
from odoo.tools.safe_eval import safe_eval


class RetentionFlowHelpers:
    """Helpers para armar, con `Form`, un documento (factura, nota de credito o
    de debito) en `doc_date` y su retencion desde la accion de su menu, igual
    que lo hace el usuario. Se mezclan en una prueba que herede de
    `RetentionTestCommon` y defina `accounting_date` y `doc_date`."""

    AMOUNT = 100000.0
    CUSTOMER_RETENTION_AMOUNT = 1000.0

    def _set_rates(self, rate_doc_date, rate_accounting_date):
        """Tasa (VEF por USD) conocida para la fecha del documento y para la
        fecha contable de la retencion."""
        Rate = self.env["res.currency.rate"]
        for date, value in (
            (self.doc_date, rate_doc_date),
            (self.accounting_date, rate_accounting_date),
        ):
            Rate.search([
                ("currency_id", "=", self.currency_usd.id),
                ("company_id", "=", self.company.id),
                ("name", "=", date),
            ]).unlink()
            Rate.create({
                "currency_id": self.currency_usd.id,
                "company_id": self.company.id,
                "name": date,
                "rate": 1 / value,
                "company_rate": 1 / value,
                "inverse_company_rate": value,
            })
        self.rate_doc_date = rate_doc_date
        self.rate_accounting_date = rate_accounting_date

    def _economic_activity(self):
        country = self.env.ref("base.ve")
        state = self.env["res.country.state"].search([("country_id", "=", country.id)], limit=1)
        municipality = self.env["res.country.municipality"].search([], limit=1) or \
            self.env["res.country.municipality"].create({
                "name": "Municipio Prueba", "code": "MUN-16179",
                "country_id": country.id, "state_id": [Command.set([state.id])],
            })
        branch = self.env["economic.branch"].search([("name", "=", "Rama 16179")], limit=1) or \
            self.env["economic.branch"].create({"name": "Rama 16179", "status": "active"})
        return self.env["economic.activity"].create({
            "name": "Actividad 16179", "aliquot": 1.5,
            "municipality_id": municipality.id, "branch_id": branch.id,
            "description": "Prueba", "minimum_monthly": 0, "minimum_annual": 0,
        })

    def _form_document(self, move_type, retention_type, amount):
        """Factura o nota de credito creada con `Form` en `doc_date`."""
        is_supplier = move_type.startswith("in_")
        journal = self.purchase_journal if is_supplier else self.sale_journal
        product = self.product_islr_one if retention_type == "islr" else self.product_iva
        with Form(self.env["account.move"].with_context(
            default_move_type=move_type, default_journal_id=journal.id,
        )) as form:
            form.partner_id = self.partner_pnr_75
            form.invoice_date = self.doc_date
            form.currency_id = self.currency_vef
            if is_supplier:
                form.correlative = str(random.randint(10000000000000, 99999999999999))
        document = form.save()
        with Form(document) as form_edit:
            with form_edit.invoice_line_ids.new() as line:
                line.product_id = product
                line.quantity = 1
                line.price_unit = amount
        document = form_edit.save()
        # En esta localizacion la fecha del documento (y de su tasa) es
        # invoice_date_display; igual que en las otras pruebas de fechas.
        document.write({"date": self.doc_date, "invoice_date_display": self.doc_date})
        return document

    def _document(self, doc_type, retention_type, amount=AMOUNT):
        """Documento publicado en `doc_date`. En esta rama no existe un
        `move_type` de nota de debito: es una factura (`out_invoice` /
        `in_invoice`) con `debit_origin_id`, que se crea con el asistente
        nativo `account.debit.note` a partir de una factura publicada."""
        if not doc_type.endswith("_debit"):
            document = self._form_document(doc_type, retention_type, amount)
            document.with_context(move_action_post_alert=True).action_post()
            return document

        origin_type = doc_type.replace("_debit", "_invoice")
        origin = self._form_document(origin_type, retention_type, amount)
        origin.with_context(move_action_post_alert=True).action_post()
        wizard = Form(self.env["account.debit.note"].with_context(
            active_model="account.move", active_ids=origin.ids,
        ))
        wizard.journal_id = origin.journal_id
        wizard.date = self.doc_date
        wizard.copy_lines = False
        debit = self.env["account.move"].browse(wizard.save().create_debit()["res_id"])
        with Form(debit) as form_debit:
            if doc_type.startswith("in_"):
                form_debit.correlative = str(random.randint(10000000000000, 99999999999999))
            with form_debit.invoice_line_ids.new() as line:
                line.product_id = (
                    self.product_islr_one if retention_type == "islr" else self.product_iva
                )
                line.quantity = 1
                line.price_unit = amount
        debit = form_debit.save()
        self.assertEqual(debit.debit_origin_id, origin)
        self.assertEqual(debit.invoice_date, self.doc_date)
        debit.with_context(move_action_post_alert=True).action_post()
        return debit

    def _retention_from_form(self, retention_type, document):
        """Retencion creada con `Form` desde la accion de su menu. IVA carga
        solo sus lineas al elegir el contacto (facturas y notas de credito);
        lo que no se carga solo (nota de debito, ISLR, municipal) se agrega
        como linea, igual que en la vista."""
        side = "client" if document.move_type.startswith("out_") else "supplier"
        action = self.env.ref(
            f"l10n_ve_payment_extension.action_retention_{retention_type}_{side}"
        ).read()[0]
        ctx = safe_eval(action.get("context", "{}"))
        view = f"l10n_ve_payment_extension.view_retention_{retention_type}_form_l10n_ve_payment_extension"
        with Form(self.env[action["res_model"]].with_context(ctx), view=view) as form:
            form.partner_id = document.partner_id
            form.date_accounting = self.accounting_date
            if side == "client":
                form.number = "%014d" % random.randint(1, 10 ** 14 - 1)
            # La nota de debito comparte contacto con su factura de origen:
            # IVA carga ambas, y la retencion es solo de la nota.
            for idx in reversed(range(len(form.retention_line_ids))):
                with form.retention_line_ids.edit(idx) as line:
                    foreign = line.move_id != document
                if foreign:
                    form.retention_line_ids.remove(idx)
            if not len(form.retention_line_ids):
                with form.retention_line_ids.new() as line:
                    line.move_id = document
                    if retention_type == "islr":
                        line.payment_concept_id = self.concept_one
                    elif retention_type == "municipal":
                        line.economic_activity_id = self._economic_activity()
            if side == "client" and retention_type == "municipal":
                # La base de la retencion municipal de cliente la escribe el
                # usuario; el monto se calcula con la alicuota de la actividad.
                with form.retention_line_ids.edit(0) as line:
                    line.invoice_amount = document.amount_untaxed
            if side == "client" and retention_type == "iva":
                # Solo en IVA de cliente el monto lo escribe el usuario; en
                # ISLR y municipal se calcula de concepto / actividad.
                with form.retention_line_ids.edit(0) as line:
                    line.retention_amount = self.CUSTOMER_RETENTION_AMOUNT
        return form.save()
