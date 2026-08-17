from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_ve_exchange_use_nd_nc = fields.Boolean(
        string='Usar Notas de Débito/Crédito para Diferencial Cambiario',
        default=False,
        help="Cuando está activado, el diferencial cambiario que queda abierto "
             "al conciliar una factura/documento en moneda extranjera NO es "
             "absorbido por el asiento automático de Odoo -- en su lugar, se "
             "documenta con una Nota de Débito (pérdida) o Nota de Crédito "
             "(ganancia) real, emitida contra la factura original y conciliada "
             "contra el residual restante.",
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
