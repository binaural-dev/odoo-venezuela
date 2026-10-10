import logging

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_withholding_common_VEF import RetentionTestCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "retention_consolidated_duplicates")
class TestRetentionConsolidatedDuplicates(RetentionTestCommon):
    """Ticket #15531 (caso #94): una factura consolidada en la retención A
    mientras su retención individual B sigue en borrador. `action_post` debe
    rechazar la emisión si la factura ya está en otro comprobante del mismo
    tipo (borrador o emitido), antes de las validaciones por
    concepto/alícuota/actividad."""

    def _post_invoice(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        self._prepare_invoice_for_retention(inv)
        inv.action_post()
        return inv

    def _line_command(self, inv, **extra):
        vals = {
            "move_id": inv.id, "payment_concept_id": self.concept_one.id,
            "invoice_type": "in_invoice", "name": "Test",
            "invoice_amount": inv.amount_untaxed, "invoice_total": inv.amount_total,
            "retention_amount": 15.0,
        }
        vals.update(extra)
        return Command.create(vals)

    def _create_retention(self, type_retention, invoices, partner=None, third_party=False, **line_extra):
        return self.env["account.retention"].create({
            "is_third_party_retention": third_party,
            "type_retention": type_retention, "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": (partner or self.partner_pnr_75).id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [self._line_command(inv, **line_extra) for inv in invoices],
        })

    def _create_activity(self, name, aliquot):
        country = self.env["res.country"].search([("code", "=", "TC14548")], limit=1) or \
            self.env["res.country"].create({"name": "Test Country 14548", "code": "TC14548"})
        state = self.env["res.country.state"].search([("code", "=", "TS14548")], limit=1) or \
            self.env["res.country.state"].create(
                {"name": "Test State 14548", "code": "TS14548", "country_id": country.id}
            )
        municipality = self.env["res.country.municipality"].search(
            [("code", "=", "MUN-14548")], limit=1
        ) or self.env["res.country.municipality"].create({
            "name": "Test Municipality 14548", "code": "MUN-14548",
            "country_id": country.id, "state_id": [Command.set([state.id])],
        })
        branch = self.env["economic.branch"].search([("name", "=", "Branch 14548")], limit=1) or \
            self.env["economic.branch"].create({"name": "Branch 14548", "status": "active"})
        return self.env["economic.activity"].create({
            "name": f"Activity {name}", "aliquot": aliquot,
            "municipality_id": municipality.id, "branch_id": branch.id,
            "description": "Test", "minimum_monthly": 0, "minimum_annual": 0,
        })

    def test_check_blocks_for_every_type_and_state(self):
        for type_retention in ("iva", "islr", "municipal"):
            for other_state in ("draft", "emitted"):
                with self.subTest(type_retention=type_retention, other_state=other_state):
                    inv = self._post_invoice()
                    other = self._create_retention(type_retention, inv)
                    if other_state == "emitted":
                        other.state = "emitted"
                    current = self._create_retention(type_retention, inv)

                    with self.assertRaises(UserError) as e:
                        current._check_duplicate_invoices_all_states()
                    self.assertIn(other.display_name, str(e.exception))
                    self.assertIn(inv.display_name, str(e.exception))

    def test_check_blocks_only_with_same_differentiator(self):
        """Misma factura, tipo y partner: solo bloquea si coincide el
        diferenciador (IVA alicuota, ISLR concepto, municipal actividad)."""
        concept_other = self.env["payment.concept"].create({"name": "Otro concepto 15531", "status": True})
        activity_1 = self._create_activity("A15531", 5.0)
        activity_2 = self._create_activity("B15531", 3.0)
        cases = {
            "iva": ({"aliquot": 16.0}, {"aliquot": 8.0}),
            "islr": ({"payment_concept_id": self.concept_one.id}, {"payment_concept_id": concept_other.id}),
            "municipal": (
                {"economic_activity_id": activity_1.id},
                {"economic_activity_id": activity_2.id},
            ),
        }
        for type_retention, (same, different) in cases.items():
            for other_state in ("draft", "emitted"):
                with self.subTest(type_retention=type_retention, other_state=other_state):
                    inv = self._post_invoice()
                    other = self._create_retention(type_retention, inv, **same)
                    other.state = other_state

                    different_ret = self._create_retention(type_retention, inv, **different)
                    different_ret._check_duplicate_invoices_all_states()

                    same_ret = self._create_retention(type_retention, inv, **same)
                    with self.assertRaises(UserError) as e:
                        same_ret._check_duplicate_invoices_all_states()
                    self.assertIn(other.display_name, str(e.exception))

    def test_check_ignores_cancelled_other_type_and_same_retention(self):
        inv = self._post_invoice()
        cancelled = self._create_retention("islr", inv)
        cancelled.action_cancel()
        self._create_retention("iva", inv)  # otro type_retention: no cuenta
        current = self._create_retention("islr", inv)

        current._check_duplicate_invoices_all_states()
        self.assertEqual(current.state, "draft")

    def test_check_ignores_retentions_of_other_partner(self):
        """Facturación a terceros (ta #65929): varios comprobantes de
        distintos terceros sobre la misma factura no se bloquean entre sí,
        para IVA, ISLR y municipal, en borrador o emitidos; el mismo partner
        sigue bloqueado."""
        other_partner = self.partner_pnr_75.copy({"name": "Third party 2", "vat": "J456"})
        for type_retention in ("iva", "islr", "municipal"):
            for other_state in ("draft", "emitted"):
                with self.subTest(type_retention=type_retention, other_state=other_state):
                    inv = self._post_invoice()
                    other = self._create_retention(
                        type_retention, inv, partner=other_partner, third_party=True,
                    )
                    other.state = other_state
                    current = self._create_retention(type_retention, inv)
                    current._check_duplicate_invoices_all_states()

                    same_partner = self._create_retention(
                        type_retention, inv, partner=other_partner, third_party=True,
                    )
                    with self.assertRaises(UserError):
                        same_partner._check_duplicate_invoices_all_states()

    def test_consolidated_invoice_cannot_be_retained_twice(self):
        inv_a = self._post_invoice()
        inv_b = self._post_invoice()
        ret_a = self._create_retention("islr", inv_a)
        ret_b = self._create_retention("islr", inv_b)

        # Consolidar la factura B dentro de la retención A.
        ret_a.write({"retention_line_ids": [self._line_command(inv_b)]})
        with self.assertRaises(UserError) as e:
            ret_a.action_post()  # B sigue en borrador con la misma factura
        self.assertIn(ret_b.display_name, str(e.exception))

        ret_b.action_cancel()
        ret_a.action_post()
        self.assertEqual(ret_a.state, "emitted")
        with self.assertRaises(UserError) as e:
            ret_b.action_post()
        self.assertIn(ret_a.display_name, str(e.exception))
        _logger.info("========= test_consolidated_invoice_cannot_be_retained_twice passed =========")

    def _post_customer_iva_invoice(self):
        inv = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self._prepare_invoice_for_retention(inv)
        inv.generate_iva_retention = True
        # l10n_ve_accountant devuelve un wizard de confirmacion en facturas de
        # cliente salvo que el contexto traiga move_action_post_alert.
        inv.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(inv.state, "posted")
        return inv

    def _consolidate_b_into_a(self):
        """Caso #94: retenciones IVA de cliente autogeneradas al publicar las
        facturas A y B; la factura B se consolida en la retencion A."""
        inv_a = self._post_customer_iva_invoice()
        inv_b = self._post_customer_iva_invoice()
        ret_a = inv_a.retention_iva_line_ids.retention_id
        ret_b = inv_b.retention_iva_line_ids.retention_id
        self.assertEqual(ret_a.state, "draft")
        self.assertEqual(ret_b.state, "draft")
        line_b_vals = ret_b.retention_line_ids[0].copy_data()[0]
        line_b_vals.pop("retention_id", None)
        ret_a.write({
            "number": "01234567891234",
            "retention_line_ids": [Command.create(line_b_vals)],
        })
        ret_b.number = "01234567891235"
        # Las lineas autogeneradas de cliente nacen con monto 0 (lo carga el usuario).
        (ret_a.retention_line_ids | ret_b.retention_line_ids).retention_amount = 24.0
        return ret_a, ret_b, inv_b

    def test_case_94_customer_iva_autogenerated_retentions(self):
        ret_a, ret_b, inv_b = self._consolidate_b_into_a()

        with self.assertRaises(UserError) as e:
            ret_a.action_post()  # B sigue en borrador con la misma factura
        self.assertIn(ret_b.display_name, str(e.exception))
        self.assertIn(inv_b.display_name, str(e.exception))

        ret_b.action_cancel()
        ret_a.action_post()
        self.assertEqual(ret_a.state, "emitted")
        with self.assertRaises(UserError) as e:
            ret_b.action_post()
        self.assertIn(ret_a.display_name, str(e.exception))

    def test_duplicate_check_in_automated_action_posts_note_and_returns_false(self):
        """En acciones automatizadas/cron el resto de las validaciones de
        action_post deja nota en el chatter y devuelve False; esta tambien."""
        ret_a, ret_b, _inv_b = self._consolidate_b_into_a()
        for ctx in ({"automated_action": True}, {"cron_id": 1}):
            with self.subTest(ctx=ctx):
                messages_before = len(ret_a.message_ids)
                self.assertFalse(ret_a.with_context(**ctx).action_post())
                self.assertEqual(ret_a.state, "draft")
                self.assertGreater(len(ret_a.message_ids), messages_before)
                self.assertIn(ret_b.display_name, ret_a.message_ids[0].body)
