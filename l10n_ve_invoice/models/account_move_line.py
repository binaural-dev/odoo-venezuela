from odoo import models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _sync_product_tax(self):
        for line in self:
            product = line.product_id
            tax_ids = line.tax_ids.ids

            if not product or not tax_ids:
                continue

            update_vals = {}
            before_links = ", ".join([tax._get_html_link() for tax in line.tax_ids])
            after = []

            if line.move_type == "in_invoice":
                after = product.supplier_taxes_id
                if set(product.supplier_taxes_id.ids) != set(tax_ids):
                    update_vals['supplier_taxes_id'] = [(6, 0, tax_ids)]
            elif line.move_type == "out_invoice":
                after = product.taxes_id
                if set(product.taxes_id.ids) != set(tax_ids):
                    update_vals['taxes_id'] = [(6, 0, tax_ids)]
            after_links = ", ".join([tax._get_html_link() for tax in after]) or "<i>No tax</i>"
            if update_vals:
                product.write(update_vals)

                product.message_post(
                    body=_(
                        """
                            <div>
                                The user %s modified the tax on invoice %s:<br/><br/>
                                %s ⟶ %s
                            </div>
                        """
                    ) % (self.env.user._get_html_link(), line.move_id._get_html_link(), after_links, before_links),
                    message_type='notification',
                    body_is_html=True
                )

    def write(self, vals):
        res = super().write(vals)
        if 'tax_ids' in vals:
            self._sync_product_tax()
        return res

    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_product_tax()
        return records