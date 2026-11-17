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

    def _check_igtf_apply_improved(self, invoice_type, company=None):
        """Indica si el IGTF aplica a un documento de este contacto segun la condicion de
        contribuyente: en ventas la de la compania, en compras la del proveedor.

        No depende de que el contacto tenga cuenta de anticipo configurada: esa cuenta solo
        se necesita para el excedente del pago y, si el contacto no la tiene, se usa la de la
        compania (ver ``_get_advance_account``).

        Args:
            invoice_type (str): move_type del documento.
            company (res.company): compania del documento. Si no se pasa, se usa la del
                contacto o, en su defecto, la compania activa.
        """
        for rec in self:
            doc_company = company or rec.company_id or self.env.company
            if invoice_type in ["out_invoice", "out_refund"]:
                return doc_company.taxpayer_type in ["special", "formal"]
            if invoice_type in ["in_invoice", "in_refund"]:
                return rec.taxpayer_type in ["special", "formal"]
            return False
        return False

    def _get_advance_account(self, partner_type, company=None):
        """Cuenta de anticipo del contacto para clientes (``customer``) o proveedores
        (``supplier``); si el contacto no la tiene configurada, la de la compania."""
        self.ensure_one()
        company = company or self.company_id or self.env.company
        if partner_type == "customer":
            return self.default_advance_customer_account_id or company.advance_customer_account_id
        return self.default_advance_supplier_account_id or company.advance_supplier_account_id
