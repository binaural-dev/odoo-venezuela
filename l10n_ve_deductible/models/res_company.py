from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    use_deductible = fields.Boolean(
        string="Use Deductibles",
        help="Allows applying a global deductible (percentage or fixed amount) "
        "to the documents selected in 'Deductible Applies To'.",
    )
    deductible_scope = fields.Selection(
        [
            ("vendor", "Vendor Bills"),
            ("customer", "Customer Invoices"),
            ("both", "Vendor Bills and Customer Invoices"),
        ],
        string="Deductible Applies To",
        default="customer",
        required=True,
    )
