from odoo import models

class MoveActionPostAlertWizard(models.TransientModel):
    _inherit = 'move.action.post.alert.wizard'

    def action_confirm(self):
        res = super(MoveActionPostAlertWizard, self).action_confirm()

        # The base action_confirm() always returns the same {'type':
        # 'ir.actions.client', 'tag': 'reload'} dict regardless of what
        # action_post() actually did (see move.action.post.alert.wizard in
        # l10n_ve_accountant), so it can't tell us whether the move was
        # really posted. Checking move_id.state directly is the only
        # reliable signal: another module's action_post() override (e.g.
        # binaural_third_party_invoice_digital, when child invoices are
        # still in draft) can return without posting the parent at all,
        # leaving it in 'draft'. Enqueueing anyway queued a document that
        # was never confirmed, letting the cron digitalize and number a
        # borrador.
        if self.move_id and self.move_id.state == 'posted' and self.env.company.invoice_digital_tfhka:
            self.move_id._tfhka_enqueue_eligible_for_digitalization()

        return res

