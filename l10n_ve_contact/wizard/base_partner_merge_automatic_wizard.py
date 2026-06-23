from odoo import models


class BasePartnerMergeAutomaticWizard(models.TransientModel):
    _inherit = "base.partner.merge.automatic.wizard"

    def _update_values(self, src_partners, dst_partner):
        merge_context = dict(self.env.context)
        merge_context.update(
            {
                "l10n_ve_partner_merge_validation": True,
                "l10n_ve_merge_partner_ids": (src_partners | dst_partner).ids,
            }
        )
        src_partners_ctx = src_partners.with_context(merge_context)
        dst_partner_ctx = dst_partner.with_context(merge_context)
        return super(
            BasePartnerMergeAutomaticWizard, self.with_context(merge_context)
        )._update_values(src_partners_ctx, dst_partner_ctx)
