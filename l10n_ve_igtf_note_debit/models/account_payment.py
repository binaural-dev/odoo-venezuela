from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _create_igtf_moves_in_payments(self, vals, write_off_line_vals=None):
        # Con el modo 'debit_note', el IGTF no se embebe como línea en este
        # mismo asiento de pago -- se genera como Nota de Débito fiscal
        # independiente. Eso lo dispara el wizard `account.payment.register`
        # (ver wizard/account_payment_register.py de este módulo) una vez
        # que el pago ya está creado y conciliado contra la factura.
        if self.company_id.igtf_note_debit_mode == "debit_note":
            return
        return super()._create_igtf_moves_in_payments(vals, write_off_line_vals)
