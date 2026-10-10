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

    def _line_command(self, inv):
        return Command.create({
            "move_id": inv.id, "payment_concept_id": self.concept_one.id,
            "invoice_type": "in_invoice", "name": "Test",
            "invoice_amount": inv.amount_untaxed, "invoice_total": inv.amount_total,
            "retention_amount": 15.0,
        })

    def _create_retention(self, type_retention, invoices, partner=None):
        return self.env["account.retention"].create({
            "type_retention": type_retention, "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": (partner or self.partner_pnr_75).id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [self._line_command(inv) for inv in invoices],
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
        other_partner = self.partner_pnr_75.copy({"name": "Third party 2"})
        for type_retention in ("iva", "islr", "municipal"):
            for other_state in ("draft", "emitted"):
                with self.subTest(type_retention=type_retention, other_state=other_state):
                    inv = self._post_invoice()
                    other = self._create_retention(type_retention, inv, partner=other_partner)
                    other.state = other_state
                    current = self._create_retention(type_retention, inv)
                    current._check_duplicate_invoices_all_states()

                    same_partner = self._create_retention(type_retention, inv, partner=other_partner)
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
