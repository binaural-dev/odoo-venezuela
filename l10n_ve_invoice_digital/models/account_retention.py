import json

from odoo import models, api, fields


class AccountRetention(models.Model):
    _inherit = ["account.retention", "tfhka.digitalization.mixin"]

    is_digitalized = fields.Boolean(string="Digitized", default=False, copy=False, tracking=True)
    show_digital_retention_iva = fields.Boolean(string="Show Digital Retention", compute="_compute_visibility_button", copy=False)
    show_digital_retention_islr = fields.Boolean(string="Show Digital Retention", compute="_compute_visibility_button", copy=False)
    control_number_tfhka = fields.Char(string="Control Number", copy=False)
    document_number_tfhka = fields.Char(string="Document Number TFHKA", copy=False)
    annulled_tfhka = fields.Boolean(string="Annulled in TFHKA", default=False, copy=False, tracking=True)
    tfhka_auto_accept_sequence_mismatch = fields.Boolean(
        default=False,
        copy=False,
        help="Equivalent to confirming the sequence-mismatch alert wizard "
             "automatically. Set before enqueueing from the automatic "
             "post-triggered flow (no human present to answer that wizard) "
             "or from the wizard itself once a human confirms it manually; "
             "read by generate_document_digital() at digitalization time, "
             "since that call is now deferred to the queue's cron and can't "
             "rely on the caller's context surviving that long.",
    )

    def generate_document_digital(self):
        self.ensure_one()
        # document_type/account_retention_alert used to be passed in by each
        # caller via with_context(); computed here instead so the call is
        # self-contained regardless of when it actually runs (the queue
        # defers it to a later cron, well after any caller-supplied context
        # would have been lost).
        document_type = "05" if self.type_retention == "iva" else "06"
        context = {"document_type": document_type}
        if self.tfhka_auto_accept_sequence_mismatch:
            context["account_retention_alert"] = True
        # All logic lives in the service layer (tfhka.retention.service),
        # including the sequence alert wizard flow.
        return self.env["tfhka.retention.service"].send_retention(
            self.with_context(**context)
        )

    def _tfhka_reconcile_success_from_log(self, log_entry):
        """See ``tfhka.digitalization.mixin._tfhka_recover_stuck_processing``.
        Unlike account.move, the retention's own document number
        (``self.number``) never gets rewritten by a successful digitalization,
        so it's safe to reuse directly instead of reading it back from the
        interrupted attempt's stored request."""
        self.ensure_one()
        response = json.loads(log_entry.response_payload)
        self.env["tfhka.retention.service"]._register_success(
            self, response, str(self.number)
        )

    def action_post(self):
        res = super().action_post()
        for retention in self:
            if (
                retention.type_retention in ("iva", "islr")
                and retention.type == "in_invoice"
                and retention.company_id.invoice_digital_tfhka
                and not retention.is_digitalized
                and retention.env.context.get("l10n_ve_invoice_digital_auto_retention")
            ):
                # No human is present to answer the sequence-mismatch alert
                # in this automatic flow, so it adopts TFHKA's correlative
                # the same way a user would by confirming that alert
                # manually (see generate_document_digital()).
                retention.tfhka_auto_accept_sequence_mismatch = True
                retention._tfhka_enqueue_digitalization()
        return res

    def action_cancel_retention(self):
        """Boton unico de anulacion: si esta digitalizada en TFHKA y no
        anulada, primero pide el motivo y anula alla (el wizard encadena
        despues la cancelacion nativa); si no, cancela directo en Odoo."""
        self.ensure_one()
        if self.is_digitalized and not self.annulled_tfhka:
            return {
                "type": "ir.actions.act_window",
                "name": "Cancel in The Factory HKA",
                "res_model": "tfhka.annul.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {"default_retention_id": self.id},
            }
        return self.action_cancel()

    @api.depends('state', 'is_digitalized')
    def _compute_visibility_button(self):
        for record in self:
            record.show_digital_retention_iva = True
            record.show_digital_retention_islr = True
            if record.state == 'emitted' and not record.is_digitalized and record.company_id.invoice_digital_tfhka:
                record.show_digital_retention_iva = False
                record.show_digital_retention_islr = False
