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
        """Indica si el IGTF aplica a un documento de este contacto según el tipo de
        contribuyente: en ventas el de la compañía del documento, en compras el del proveedor.

        No depende de que haya cuenta de anticipo (del contacto o de la compañía): esa cuenta
        solo se usa para el excedente del pago (ver ``_l10n_ve_get_advance_account``).

        :param invoice_type: move_type del documento.
        :param company: res.company del documento; si no se pasa, la del contacto o la activa.
        """
        for rec in self:
            doc_company = company or rec.company_id or self.env.company
            if invoice_type in ["out_invoice", "out_refund"]:
                return doc_company.taxpayer_type in ["special", "formal"]
            if invoice_type in ["in_invoice", "in_refund"]:
                return rec.taxpayer_type in ["special", "formal"]
            return False
        return False
