from odoo import models, _


class BinauralPaymentExtensionRetentionIvaVoucher(models.AbstractModel):
    _inherit = "report.binaural_payment_extension.retention_voucher_template"

    def get_digits(self):
        return 2
