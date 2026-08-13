from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_ve_exchange_use_nd_nc = fields.Boolean(
        string='Use Debit/Credit Notes for Exchange Differences',
        default=False,
        help="When enabled, the exchange rate difference left open when reconciling "
             "a foreign-currency invoice/bill is NOT absorbed by Odoo's automatic "
             "journal entry -- instead, it's documented as a real Debit Note (loss) "
             "or Credit Note (gain), issued against the original invoice and "
             "reconciled against the leftover residual.",
    )

    l10n_ve_exchange_note_product_id = fields.Many2one(
        'product.product',
        string='Producto de Nota de Diferencial Cambiario',
        help="Producto usado como línea de las Notas de Débito/Crédito de "
             "diferencial cambiario. Debe tener asignado el impuesto Exento "
             "de venta y de compra (l10n_ve_accountant: exent_aliquot_sale / "
             "exent_aliquot_purchase) -- el diferencial cambiario no es base "
             "de IVA, pero l10n_ve_accountant exige un impuesto en cada línea.",
    )
