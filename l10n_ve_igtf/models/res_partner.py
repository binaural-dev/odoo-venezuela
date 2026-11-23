from odoo import fields, models, _ , api


class ResPartner(models.Model):
    _inherit = "res.partner"

    default_advance_customer_account_id= fields.Many2one(
        "account.account", 
        domain=[("account_type", "=", "liability_current"), ("is_advance_account", "=", True),('reconcile','=',True)], 
        copy=False, 
        default=lambda self: self.env.company.advance_customer_account_id,
    )

    default_advance_supplier_account_id= fields.Many2one(
        "account.account", 
        domain=[("account_type", "=", "asset_current"),("is_advance_account", "=", True),('reconcile','=',True)], 
        copy=False, 
        default=lambda self: self.env.company.advance_supplier_account_id,
    )

    def _l10n_ve_get_advance_account(self, company, partner_type):
        """Cuenta de anticipos del contacto para `company`.

        default_advance_*_account_id no depende de la compañía: un contacto compartido guarda una
        sola cuenta, que puede ser de otra compañía (la migración de v17 o el default con la
        compañía activa al crearlo). Usarla da error de acceso a account.account o, si el usuario
        tiene acceso a esa compañía, lleva el anticipo a la cuenta de otra empresa. Se usa la del
        contacto solo si es de `company` (o de una compañía padre); si no, la de la compañía, como
        en v17.

        :param company: res.company del documento (pago, factura, asiento).
        :param partner_type: "customer" o "supplier".
        :return: account.account, vacío si ninguna está configurada.
        """
        customer = partner_type == "customer"
        partner_field = (
            "default_advance_customer_account_id" if customer else "default_advance_supplier_account_id"
        )
        # sudo: la cuenta puede ser de una compañía sin acceso; solo se lee su compañía.
        account = self[:1].sudo()[partner_field]
        if account and account.company_ids & company.sudo().parent_ids:
            return self.env["account.account"].browse(account.id)
        return company.advance_customer_account_id if customer else company.advance_supplier_account_id

    def _check_igtf_apply_improved(self, invoice_type, company=None):
        for rec in self:
            company = company or self.company_id or self.env.company
            company_taxpayer_type = company.taxpayer_type
            
            # 2. Manejo de Ventas (out_invoice)
            if invoice_type in ["out_invoice","out_refund"] and rec._l10n_ve_get_advance_account(company, "customer"):
                return company_taxpayer_type in ['special','formal']
                
            # 3. Manejo de Compras (in_invoice)
            elif invoice_type in ["in_invoice","in_refund"] and rec._l10n_ve_get_advance_account(company, "supplier"):
                partner_taxpayer_type = rec.taxpayer_type
                
                return partner_taxpayer_type in ['special','formal']
                
            return False