import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression

_logger = logging.getLogger(__name__)

from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"
    
    guide_number = fields.Char(
        tracking=True, 
        copy=False,
    )

    state_guide_dispatch = fields.Selection(
        [
            ("to_invoice", "To Invoice"), 
            ("invoiced", "Invoiced"), 
        ], 
        default="to_invoice",
    )

    show_create_invoice = fields.Boolean(compute='_compute_button_visibility')
    show_create_bill = fields.Boolean(compute='_compute_button_visibility')
    show_create_customer_credit = fields.Boolean(compute='_compute_button_visibility')
    show_create_vendor_credit = fields.Boolean(compute='_compute_button_visibility')
    
    has_document = fields.Boolean(
        string="Has Document",
        compute="_compute_has_document",
        help="Technical field to check if the related sale order has a document.",
    )

    document = fields.Selection(related="sale_id.document")

    transfer_reason_id = fields.Many2one(
        'transfer.reason', 
        string="Reason for Transfer",
        domain="[('id', 'in', allowed_reason_ids)]",
        tracking=True,
    )

    allowed_reason_ids = fields.Many2many(
        'transfer.reason',
        string="Allowed Reasons",
        store=True,
        compute="_compute_allowed_reason_ids",
    )

    is_donation = fields.Boolean(related="sale_id.is_donation")

    is_dispatch_guide = fields.Boolean(string="Is Dispatch Guide", default=False, tracking=True)

    @api.depends('is_donation', 'is_dispatch_guide')
    def _compute_allowed_reason_ids(self):
        for picking in self:
            domain = []

            # Obtener las razones de transferencia
            donation_reason = self.env.ref('l10n_ve_stock_account.transfer_reason_donation', raise_if_not_found=False)
            consignment_reason = self.env.ref('l10n_ve_stock_account.transfer_reason_consignment', raise_if_not_found=False)
            internal_reason = self.env.ref('l10n_ve_stock_account.transfer_reason_internal_transfer', raise_if_not_found=False)

            # Lista de IDs permitidos
            allowed_reason_ids = []

            # Donations
            if picking.is_donation and donation_reason:
                allowed_reason_ids.append(donation_reason.id)
                picking.transfer_reason_id = donation_reason.id

            # Dispatch Guide
            elif picking.is_dispatch_guide:
                if consignment_reason:
                    allowed_reason_ids.append(consignment_reason.id)
                if internal_reason:
                    allowed_reason_ids.append(internal_reason.id)
                picking.transfer_reason_id = internal_reason.id if internal_reason else False

            # Clear the transfer reason if there are no allowed reasons
            else:
                picking.transfer_reason_id = False

            if allowed_reason_ids:
                domain = [('id', 'in', allowed_reason_ids)]

            picking.allowed_reason_ids = self.env['transfer.reason'].search(domain)


    def _set_guide_number(self):
        for picking in self:
            picking.guide_number = picking.get_sequence_guide_num()

    @api.model
    def get_sequence_guide_num(self):
        self.ensure_one()
        sequence = self.env["ir.sequence"].sudo()
        guide_number = None

        guide_number = sequence.search(
            [("code", "=", "guide.number"), ("company_id", "=", self.company_id.id)]
        )
        if not guide_number:
            guide_number = sequence.create(
                {
                    "name": "Guide Number",
                    "code": "guide.number",
                    "company_id": self.company_id.id,
                    "prefix": "GUIDE",
                    "padding": 5,
                }
            )
        return guide_number.next_by_id(guide_number.id)
    
    @api.depends('invoice_count', 'state', 'state_guide_dispatch', 'operation_code', 'is_return')
    def _compute_button_visibility(self):
        for record in self:
            record.show_create_invoice = all([
                record.invoice_count == 0,
                record.state == 'done',
                record.state_guide_dispatch == 'to_invoice',
                record.operation_code != 'incoming',
                not record.is_return
            ])
            
            record.show_create_bill = all([
                record.invoice_count == 0,
                record.state == 'done',
                record.state_guide_dispatch == 'to_invoice',
                record.operation_code != 'outgoing',
                not record.is_return
            ])
            
            record.show_create_customer_credit = all([
                record.invoice_count == 0,
                record.state == 'done',
                record.state_guide_dispatch == 'to_invoice',
                record.operation_code != 'outgoing',
                record.is_return
            ])
            
            record.show_create_vendor_credit = all([
                record.invoice_count == 0,
                record.state == 'done',
                record.state_guide_dispatch == 'to_invoice',
                record.operation_code != 'incoming',
                record.is_return
            ])

    def create_invoice_lots(self):
        valid_picking = self.filtered(
            lambda picking: picking.state_guide_dispatch == "invoiced"
        )
        
        if valid_picking:
            raise UserError(_("You cannot create an invoice from this picking for this state."))
            
        for picking in self:
            if picking.show_create_invoice:
                picking.create_invoice()
            elif picking.show_create_bill:
                picking.create_bill()
            elif picking.show_create_customer_credit:
                picking.create_customer_credit()
            elif picking.show_create_vendor_credit:
                picking.create_vendor_credit()

    def create_invoice(self):
        """
        Creates customer invoice from the picking
        """
        self._validate_one_invoice_posted()
        for picking_id in self:
            current_user = self.env.uid
            if picking_id.picking_type_id.code == 'outgoing':
                customer_journal_id = \
                    picking_id.env['ir.config_parameter'].sudo(). \
                        get_param('stock_move_invoice.customer_journal_id') or \
                    False
                if not customer_journal_id:
                    raise UserError(
                        _("Please configure the journal from settings"))

                invoice_line_list = picking_id._get_invoice_lines_for_invoice()
                origin_name = self._get_origin_name(picking_id)
                self.env['account.move'].create({
                    'move_type': 'out_invoice',
                    'invoice_origin': origin_name,
                    'invoice_user_id': current_user,
                    'narration': picking_id.name,
                    'partner_id': picking_id.partner_id.id,
                    'currency_id': picking_id.env.user.company_id.currency_id.id,
                    'journal_id': int(customer_journal_id),
                    'payment_reference': picking_id.name,
                    'picking_id': picking_id.id,
                    'invoice_line_ids': invoice_line_list,
                    'transfer_ids': self
                })
            picking_id.state_guide_dispatch = 'invoiced'
        return True 

    def _get_invoice_lines_for_invoice(self):
        self.ensure_one()
        invoice_line_list = []
        for move_id in self.move_ids_without_package:
            price_unit = move_id.product_id.list_price
            tax_ids = [
                (
                    6,
                    0,
                    [self.company_id.account_sale_tax_id.id]
                )
            ]
            if move_id.sale_line_id:
                price_unit = move_id.sale_line_id.price_unit
                tax_ids = [
                    (
                        6,
                        0,
                        move_id.sale_line_id.tax_id.ids
                    )
                ]

            vals = (0, 0, {
                'name': move_id.description_picking,
                'product_id': move_id.product_id.id,
                'price_unit': price_unit,
                'account_id': (
                    move_id.product_id.property_account_income_id.id
                    if move_id.product_id.property_account_income_id
                    else move_id.product_id.categ_id.property_account_income_categ_id.id
                ),
                'tax_ids': tax_ids,
                'quantity': move_id.quantity_done,
            })
            invoice_line_list.append(vals)
        return invoice_line_list

    def _action_done(self):
        res = super()._action_done()
        self._set_guide_number()
        # TODO Add picking type logic either here or in the set_guide_number method
        return res
    

    def print_dispatch_guide(self):
        return self.env.ref("l10n_ve_stock_account.action_dispatch_guide").read()[0]


    def get_foreign_currency_is_vef(self):
        return self.company_id.currency_foreign_id == self.env.ref("base.VEF")

    def get_digits(self):
        return self.env.ref("base.VEF").decimal_places


    @api.depends('sale_id.document')
    def _compute_has_document(self):
        for picking in self:
            picking.has_document = bool(picking.sale_id.document)

    def get_totals(self, use_foreign_currency=False):
        """
        """
        self.ensure_one()
        totals = {
            'subtotal': 0.0,
            'tax': 0.0,
            'total': 0.0,
        }

        for line in self.move_ids_without_package:
            line_values = line._get_line_values(use_foreign_currency=use_foreign_currency)
            totals['subtotal'] += line_values['subtotal_after_discount']
            totals['tax'] += line_values['tax_amount']
            totals['total'] += line_values['total']

        return totals

    
    def create_bill(self):
        self._validate_one_invoice_posted()
        res = super().create_bill()
        for picking in self:
            picking.state_guide_dispatch = 'invoiced'
        return res

    
    def create_customer_credit(self):
        self._validate_one_invoice_posted()
        res = super().create_customer_credit()
        for picking in self:
            picking.state_guide_dispatch = 'invoiced'
        return res
    
    def create_vendor_credit(self):
        self._validate_one_invoice_posted()
        res = super().create_vendor_credit()
        for picking in self:
            picking.state_guide_dispatch = 'invoiced'
        return res
    
    def _validate_one_invoice_posted(self,):
        for picking in self:
            invoice_ids = self.env['account.move'].search(
                [
                    ('picking_id', '=', picking.id),
                    ("state", "=", "posted")
                ]
            )            
            if invoice_ids:
                raise UserError(
                    _(
                        "This guide has at least one posted invoice, please check your invoice."
                    )
                )

    def _get_origin_name(self, picking):
        if picking.picking_type_id.code == 'outgoing':
            if picking.sale_id:
                return picking.sale_id.name
        return picking.name