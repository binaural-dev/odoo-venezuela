from odoo import fields, models, api, _
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = "res.company"


    igtf_note_debit_mode = fields.Selection(
        [
            ("inline", "Línea en el mismo asiento (flujo actual)"),
            ("debit_note", "Nota de Débito Fiscal automática (nuevo flujo)"),
        ],
        string="Modo de Percepción de IGTF",
        default="inline",
        required=True,
        copy=False,
        help="Determina cómo se registra la percepción de IGTF:\n"
             "- Línea en el mismo asiento: comportamiento histórico de l10n_ve_igtf.\n"
             "- Nota de Débito Fiscal automática: genera un documento fiscal "
             "independiente (ND) vinculado a la factura de origen, conforme a "
             "las Providencias SENIAT 0071/0102.",
    )


    igtf_note_debit_product_id = fields.Many2one(
        "product.product",
        string="Producto de Percepción de IGTF",
        copy=False,
        help="Producto usado como única línea de la Nota de Débito de IGTF. "
             "Debe llevar asignado el impuesto Exento/No Sujeto de venta y "
             "compra (campos 'exent_aliquot_sale' / 'exent_aliquot_purchase' "
             "de l10n_ve_accountant) -- IGTF no es base de IVA, pero "
             "l10n_ve_accountant exige que todo producto tenga exactamente "
             "un impuesto de venta y uno de compra asignados.",
    )

    igtf_note_debit_include_in_payment_default = fields.Boolean(
        string="Incluir IGTF en el pago por defecto",
        default=True,
        copy=False,
        help="Valor por defecto del check 'Incluir IGTF en el pago' en el "
             "wizard de registro de pago, cuando 'Modo de Percepción de "
             "IGTF' es 'Nota de Débito Fiscal automática'. El usuario puede "
             "marcarlo o desmarcarlo en cada pago individual; esto solo "
             "define con qué valor arranca.",
    )

    igtf_note_debit_vef_journal_id = fields.Many2one(
        "account.journal",
        string="Diario VEF para cobro de IGTF",
        copy=False,
        help="Diario en Bolívares (VEF) usado para registrar el pago aparte "
             "del IGTF cuando el 'Modo de Cobro del IGTF' es 'Registrar el "
             "IGTF como pago aparte en VEF'. Si no se configura, se busca "
             "automáticamente el primer diario de banco/caja en VEF que no "
             "esté marcado como IGTF.",
    )

    igtf_note_debit_valid_journal_ids = fields.Json(
        string="IDs de diarios VEF válidos para IGTF",
        compute="_compute_igtf_note_debit_valid_journal_ids",
        help="Lista (JSON) de los IDs de account.journal que cumplen los "
             "requisitos para ser el Diario VEF de cobro de IGTF: tipo "
             "banco/caja, no marcado como diario IGTF, y en moneda "
             "Bolívares (VEF) -- ya sea explícita o implícita (sin "
             "moneda propia, cuando la moneda de la compañía es VEF).",
    )

    @api.depends("currency_id")
    def _compute_igtf_note_debit_valid_journal_ids(self):
        Journal = self.env["account.journal"]
        vef = self.env.ref("base.VEF")
        for company in self:
            domain = [
                ("company_id", "=", company.id),
                ("type", "in", ("bank", "cash")),
                ("is_igtf", "!=", True),
            ]
            if company.currency_id == vef:
                domain += ["|", ("currency_id", "=", vef.id), ("currency_id", "=", False)]
            else:
                domain += [("currency_id", "=", vef.id)]
            journals = Journal.search(domain)
            company.igtf_note_debit_valid_journal_ids = journals.ids

    igtf_note_debit_valid_product_ids = fields.Json(
        string="IDs de productos válidos para IGTF",
        compute="_compute_igtf_note_debit_valid_product_ids",
        help="Lista (JSON) de los IDs de product.product que cumplen los "
             "requisitos para ser el Producto de Percepción de IGTF: tipo "
             "Servicio, cuenta de ingreso/gasto igual a la cuenta de IGTF "
             "de cliente/proveedor configurada en Ajustes > Contabilidad > "
             "IGTF, e impuesto de venta/compra igual al impuesto Exento "
             "configurado en Ajustes > Contabilidad > Régimen Fiscal "
             "(exent_aliquot_sale / exent_aliquot_purchase).",
    )

    @api.depends(
        "customer_account_igtf_id",
        "supplier_account_igtf_id",
        "exent_aliquot_sale",
        "exent_aliquot_purchase",
    )
    def _compute_igtf_note_debit_valid_product_ids(self):
        Product = self.env["product.product"]
        for company in self:
            if not (
                company.customer_account_igtf_id
                and company.supplier_account_igtf_id
                and company.exent_aliquot_sale
                and company.exent_aliquot_purchase
            ):
                company.igtf_note_debit_valid_product_ids = []
                continue
            domain = [
                ("type", "=", "service"),
                ("property_account_income_id", "=", company.customer_account_igtf_id.id),
                ("property_account_expense_id", "=", company.supplier_account_igtf_id.id),
                ("taxes_id", "in", company.exent_aliquot_sale.id),
                ("supplier_taxes_id", "in", company.exent_aliquot_purchase.id),
                ("company_id", "in", (company.id, False)),
            ]
            products = Product.search(domain)
            company.igtf_note_debit_valid_product_ids = products.ids

    @api.constrains("igtf_note_debit_mode", "igtf_note_debit_product_id")
    def _check_igtf_note_debit_config(self):
        for company in self:
            if self.env.context.get("install_mode") or self.env.context.get("skip_check"):
                continue
            if company.igtf_note_debit_mode == "debit_note" and not company.igtf_note_debit_product_id:
                raise UserError(_(
                    "Para usar el modo 'Nota de Débito Fiscal automática' debe "
                    "configurar el producto de Percepción de IGTF en Ajustes > "
                    "Contabilidad > IGTF."
                ))
