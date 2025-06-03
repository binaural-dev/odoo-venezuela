from odoo.exceptions import UserError
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    invoice_count = fields.Integer(string="Invoices", compute="_compute_invoice_count")
    invoice_ids = fields.Many2many(
        comodel_name="account.move",
        string="Invoices",
        compute="_compute_invoice_ids",
        search="_search_invoice_ids",
        copy=False,
    )
    operation_code = fields.Selection(related="picking_type_id.code")
    is_return = fields.Boolean()

    guide_number = fields.Char(
        tracking=True,
        copy=False,
    )

    state_guide_dispatch = fields.Selection(
        [
            ("to_invoice", "To Invoice"),
            ("invoiced", "Invoiced"),
            ("invoiced_partial", "Partially Invoiced"),
            ("emited", "Emited"),
        ],
        default="to_invoice",
    )

    show_create_invoice = fields.Boolean(compute="_compute_button_visibility")
    show_create_bill = fields.Boolean(compute="_compute_button_visibility")
    show_create_customer_credit = fields.Boolean(compute="_compute_button_visibility")
    show_create_vendor_credit = fields.Boolean(compute="_compute_button_visibility")
    show_create_invoice_internal = fields.Boolean(compute="_compute_button_visibility")

    show_other_causes_transfer_reason = fields.Boolean(compute="_compute_show_other_causes_transfer_reason")

    has_document = fields.Boolean(
        string="Has Document",
        compute="_compute_has_document",
        help="Technical field to check if the related sale order has a document.",
    )

    document = fields.Selection(related="sale_id.document")

    transfer_reason_id = fields.Many2one(
        "transfer.reason",
        string="Reason for Transfer",
        domain="[('id', 'in', allowed_reason_ids)]",
        tracking=True,
    )

    other_causes_transfer_reason = fields.Char(
        string="Reason for transfer for other reasons",
        copy=False
    )

    allowed_reason_ids = fields.Many2many(
        "transfer.reason",
        string="Allowed Reasons",
        store=True,
        compute="_compute_allowed_reason_ids",
    )

    is_donation = fields.Boolean(related="sale_id.is_donation")

    is_dispatch_guide = fields.Boolean(
        string="Is Dispatch Guide",
        default=True,
        tracking=True,
        store=True,
        compute="_compute_is_dispatch_guide",
    )
    partner_required = fields.Boolean(compute='_compute_partner_required', store=True)
    
    is_consignment = fields.Boolean(compute="_compute_is_consignment", store=True)
    is_consignment_readonly = fields.Boolean(default=False)

    def action_open_invoice_wizard(self):
        return {
            "name": "Generate Invoice For Multiple Picking",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "picking.invoice.wizard",  
            "views": [(self.env.ref('l10n_ve_stock_account.picking_invoice_wizard_view_form').id, "form")],
            "type": "ir.actions.act_window",
            "target": "new",
        }
    
    # This field controls the visibility of the button, determines when to generate
    # the dispatch guide sequence, and controls the visibility of the 'guide_number' field.
    dispatch_guide_controls = fields.Boolean(
        compute="_compute_dispatch_guide_controls", store=True
    )

    invoice_state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("posted", "Posted"),
            ("cancel", "Canceled"),
        ],
        string="Invoice State",
        compute="_compute_invoice_state",
    )

    order_is_consignment = fields.Boolean(compute="_compute_order_is_consignment")

    location_id = fields.Many2one(compute="_compute_location_id")

    def _set_guide_number(self):
        for picking in self:
            if picking.dispatch_guide_controls:
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

    # === MAIN FUNCTIONS ===#

    def create_multi_invoice(self, pickings):

        
        lines = self._get_multiple_invoice_lines_for_invoice(pickings, from_picking_line=True)
        current_user = self.env.uid

        if self.picking_type_id.code == "outgoing":
            customer_journal_id = self.env.company.customer_journal_id or False
            if not customer_journal_id:
                raise UserError(_("Please configure the journal from settings"))
            lines = self._get_multiple_invoice_lines_for_invoice(pickings, from_picking_line=True)
            origin_name = '/'.join(pickings.mapped('name'))
            
            origins_invoice = '/'.join([self._get_origin_name(picking) for picking in pickings])
            _logger.warning(origins_invoice)
            invoice = self.env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "invoice_origin": origins_invoice, 
                    "invoice_user_id": current_user,
                    "narration": origin_name,
                    "partner_id": self.partner_id.id,
                    "currency_id": self.env.user.company_id.currency_id.id,
                    "journal_id": int(customer_journal_id),
                    "picking_ids": pickings,
                    "invoice_line_ids": lines,
                    "transfer_ids": [(6, 0, pickings.ids)],
                    "from_picking": True,
                }
            )
            for picking_id in pickings:
                picking_id.write({"state_guide_dispatch": "invoiced"})
                picking_id._update_order_sale_invoiced()
            return invoice    

    def create_invoice(self):
        """
        Creates customer invoice from the picking
        """
        self._validate_one_invoice_posted()
        for picking_id in self:
            current_user = self.env.uid
            if picking_id.picking_type_id.code == "outgoing":
                customer_journal_id = self.env.company.customer_journal_id or False
                if not customer_journal_id:
                    raise UserError(_("Please configure the journal from settings"))

                invoice_line_list = picking_id._get_invoice_lines_for_invoice(
                    from_picking_line=True
                )
                origin_name = self._get_origin_name(picking_id)
                invoice = self.env["account.move"].create(
                    {
                        "move_type": "out_invoice",
                        "invoice_origin": origin_name, 
                        "invoice_user_id": current_user,
                        "narration": picking_id.name,
                        "partner_id": picking_id.partner_id.id,
                        "currency_id": picking_id.env.user.company_id.currency_id.id,
                        "journal_id": int(customer_journal_id),
                        "payment_reference": picking_id.name,
                        "picking_ids": picking_id,
                        "invoice_line_ids": invoice_line_list,
                        "transfer_ids": self,
                        "from_picking": True,
                    }
                )
            picking_id.write({"state_guide_dispatch": "invoiced"})
            picking_id._update_order_sale_invoiced()
        return invoice

    def create_bill(self):
        """This is the function for creating vendor bill
        from the picking"""
        self._validate_one_invoice_posted()
        for picking_id in self:
            current_user = self.env.uid
            if picking_id.picking_type_id.code == "incoming":
                vendor_journal_id = self.env.company.vendor_journal_id
                if not vendor_journal_id:
                    raise UserError(
                        _("Please configure the journal from the settings.")
                    )
                invoice_line_list = []
                for move_ids_without_package in picking_id.move_ids_without_package:
                    vals = (
                        0,
                        0,
                        {
                            "name": move_ids_without_package.description_picking,
                            "product_id": move_ids_without_package.product_id.id,
                            "price_unit": move_ids_without_package.product_id.lst_price,
                            "account_id": (
                                move_ids_without_package.product_id.property_account_income_id.id
                                if move_ids_without_package.product_id.property_account_income_id
                                else move_ids_without_package.product_id.categ_id.property_account_income_categ_id.id
                            ),
                            "tax_ids": [
                                (
                                    6,
                                    0,
                                    [picking_id.company_id.account_purchase_tax_id.id],
                                )
                            ],
                            "quantity": move_ids_without_package.quantity,
                            "from_picking_line": True,
                        },
                    )
                    invoice_line_list.append(vals)
                    invoice = picking_id.env["account.move"].create(
                        {
                            "move_type": "in_invoice",
                            "invoice_origin": picking_id.name,
                            "invoice_user_id": current_user,
                            "narration": picking_id.name,
                            "partner_id": picking_id.partner_id.id,
                            "currency_id": picking_id.env.user.company_id.currency_id.id,
                            "journal_id": int(vendor_journal_id),
                            "payment_reference": picking_id.name,
                            "picking_id": picking_id.id,
                            "invoice_line_ids": invoice_line_list,
                            "transfer_ids": self,
                            "from_picking": True,
                        }
                    )
                    # invoice.with_context(move_action_post_alert=True).action_post()
                picking_id.write({"state_guide_dispatch": "invoiced"})
                picking_id._update_order_sale_invoiced()
            return invoice

    def create_customer_credit(self):
        """This is the function for creating customer credit note
        from the picking"""
        self._validate_one_invoice_posted()
        for picking_id in self:
            current_user = picking_id.env.uid
            if picking_id.picking_type_id.code == "incoming":
                customer_journal_id = self.env.company.customer_journal_id
                if not customer_journal_id:
                    raise UserError(_("Please configure the journal from settings"))
                invoice_line_list = []
                for move_ids_without_package in picking_id.move_ids_without_package:
                    vals = (
                        0,
                        0,
                        {
                            "name": move_ids_without_package.description_picking,
                            "product_id": move_ids_without_package.product_id.id,
                            "price_unit": move_ids_without_package.product_id.lst_price,
                            "account_id": (
                                move_ids_without_package.product_id.property_account_income_id.id
                                if move_ids_without_package.product_id.property_account_income_id
                                else move_ids_without_package.product_id.categ_id.property_account_income_categ_id.id
                            ),
                            "tax_ids": [
                                (6, 0, [picking_id.company_id.account_sale_tax_id.id])
                            ],
                            "quantity": move_ids_without_package.quantity,
                            "from_picking_line": True,
                        },
                    )
                    invoice_line_list.append(vals)
                    invoice = picking_id.env["account.move"].create(
                        {
                            "move_type": "out_refund",
                            "invoice_origin": picking_id.name,
                            "invoice_user_id": current_user,
                            "narration": picking_id.name,
                            "partner_id": picking_id.partner_id.id,
                            "currency_id": picking_id.env.user.company_id.currency_id.id,
                            "journal_id": customer_journal_id,
                            "payment_reference": picking_id.name,
                            "picking_id": picking_id.id,
                            "invoice_line_ids": invoice_line_list,
                            "transfer_ids": self,
                            "from_picking_line": True,
                        }
                    )
                    # invoice.with_context(move_action_post_alert=True).action_post()
                picking_id.write({"state_guide_dispatch": "invoiced"})
                picking_id._update_order_sale_invoiced()
            return invoice

    def create_vendor_credit(self):
        """This is the function for creating refund
        from the picking"""
        self._validate_one_invoice_posted()
        for picking_id in self:
            current_user = self.env.uid
            if picking_id.picking_type_id.code == "outgoing":
                vendor_journal_id = self.env.company.vendor_journal_id
                if not vendor_journal_id:
                    raise UserError(
                        _("Please configure the journal from the settings.")
                    )
                invoice_line_list = []
                for move_ids_without_package in picking_id.move_ids_without_package:
                    vals = (
                        0,
                        0,
                        {
                            "name": move_ids_without_package.description_picking,
                            "product_id": move_ids_without_package.product_id.id,
                            "price_unit": move_ids_without_package.product_id.lst_price,
                            "account_id": (
                                move_ids_without_package.product_id.property_account_income_id.id
                                if move_ids_without_package.product_id.property_account_income_id
                                else move_ids_without_package.product_id.categ_id.property_account_income_categ_id.id
                            ),
                            "tax_ids": [
                                (
                                    6,
                                    0,
                                    [picking_id.company_id.account_purchase_tax_id.id],
                                )
                            ],
                            "quantity": move_ids_without_package.quantity,
                            "from_picking_line": True,
                        },
                    )
                    invoice_line_list.append(vals)
                    invoice = picking_id.env["account.move"].create(
                        {
                            "move_type": "in_refund",
                            "invoice_origin": picking_id.name,
                            "invoice_user_id": current_user,
                            "narration": picking_id.name,
                            "partner_id": picking_id.partner_id.id,
                            "currency_id": picking_id.env.user.company_id.currency_id.id,
                            "journal_id": int(vendor_journal_id),
                            "payment_reference": picking_id.name,
                            "picking_id": picking_id.id,
                            "invoice_line_ids": invoice_line_list,
                            "transfer_ids": self,
                            "from_picking_line": True,
                        }
                    )
                    # invoice.with_context(move_action_post_alert=True).action_post()
                picking_id.write({"state_guide_dispatch": "invoiced"})
                picking_id._update_order_sale_invoiced()
            return invoice

    def _update_order_sale_invoiced(self):
        for picking in self:
            if picking.sale_id:
                picking.sale_id.write({"invoice_status": "invoiced"})
                for line in picking.sale_id.order_line:
                    line.write({"qty_invoiced": line.qty_invoiced + line.qty_delivered})

    def _get_invoice_lines_for_invoice(self, from_picking_line=False):
        self.ensure_one()
        invoice_line_list = []
        for move_id in self.move_ids_without_package:
            price_unit = move_id.product_id.list_price
            tax_ids = [(6, 0, [self.company_id.account_sale_tax_id.id])]
            if move_id.sale_line_id:
                price_unit = move_id.sale_line_id.price_unit
                tax_ids = [(6, 0, move_id.sale_line_id.tax_id.ids)]

            vals = (
                0,
                0,
                {
                    "name": move_id.description_picking,
                    "product_id": move_id.product_id.id,
                    "price_unit": price_unit,
                    "account_id": (
                        move_id.product_id.property_account_income_id.id
                        if move_id.product_id.property_account_income_id
                        else move_id.product_id.categ_id.property_account_income_categ_id.id
                    ),
                    "tax_ids": tax_ids,
                    "quantity": move_id.quantity,
                    "from_picking_line": from_picking_line,
                },
            )
            invoice_line_list.append(vals)
        return invoice_line_list
    
    def _get_multiple_invoice_lines_for_invoice(self,pickings, from_picking_line=False):
        self.ensure_one()
        invoice_line_list = []

        for picking in pickings:
            for move_id in picking.move_ids_without_package:
                price_unit = move_id.product_id.list_price
                tax_ids = [(6, 0, [self.company_id.account_sale_tax_id.id])]
                if move_id.sale_line_id:
                    price_unit = move_id.sale_line_id.price_unit
                    tax_ids = [(6, 0, move_id.sale_line_id.tax_id.ids)]

                vals = (
                    0,
                    0,
                    {
                        "name": move_id.description_picking,
                        "product_id": move_id.product_id.id,
                        "price_unit": price_unit,
                        "account_id": (
                            move_id.product_id.property_account_income_id.id
                            if move_id.product_id.property_account_income_id
                            else move_id.product_id.categ_id.property_account_income_categ_id.id
                        ),
                        "tax_ids": tax_ids,
                        "quantity": move_id.quantity,
                        "from_picking_line": from_picking_line,
                    },
                )
                invoice_line_list.append(vals)
                invoice_line_list = self.group_products(invoice_line_list)
        return invoice_line_list
    
    # === OVERRIDES ===#

    def _action_done(self):
        res = super()._action_done()
        self._set_guide_number()
        # TODO Add picking type logic either here or in the set_guide_number method
        return res

    def get_foreign_currency_is_vef(self):

        res = self.company_id.currency_foreign_id == self.env.ref("base.VEF")
        return res

    # === METHODS ===#

    def group_products(self, product_list):
                grouped_products = {}
                for _, _, product in product_list:
                    product_id = product['product_id']
                    if product_id in grouped_products:
                        grouped_products[product_id]['quantity'] += product['quantity']
                    else:
                        grouped_products[product_id] = product
                return [(0, 0, product) for product in grouped_products.values()]

    def get_digits(self):
        return self.env.ref("base.VEF").decimal_places

    def print_dispatch_guide(self):
        return self.env.ref("l10n_ve_stock_account.action_dispatch_guide").read()[0]

    def _validate_one_invoice_posted(self):
        for picking in self:
            invoice_ids = self.env["account.move"].search(
                [("picking_ids", "=", picking.id), ("state", "=", "posted")]
            )
            if invoice_ids:
                raise UserError(
                    _(
                        "This guide has at least one posted invoice, please check your invoice."
                    )
                )

    def _get_origin_name(self, picking):
        if picking.operation_code == "outgoing":
            if picking.sale_id:
                return picking.sale_id.name
        if picking.operation_code == "internal":
            if picking.transfer_reason_id:
                return picking.transfer_reason_id.name
        return picking.name

    def _pre_action_done_hook(self):
        res = super()._pre_action_done_hook()

        # TODO: agregar alerta cuando sea de self_consumption_reason
        #
        # contexto del problema y TODO:
        #
        # El código comentado funciona para crear la alerta pero dejan de aparecer
        # en la interfaz las alertas nativas de Odoo para entrega parcial y demás.
        #
        # Objetivo: hacer funcionar todas las alertas y que la existencia de la declarada acá
        # no minimize la alerta de Odoo nativo.
        #
        # if self.env.context.get("skip_self_consumption_check"):
        #     return res  # Evita bucles infinitos
        #
        # self_consumption_reason = self.env.ref(
        #     "l10n_ve_stock_account.transfer_reason_self_consumption",
        #     raise_if_not_found=False
        # )
        #
        # for picking in self:
        #     if picking.transfer_reason_id.id == self_consumption_reason.id:
        #         return {
        #             'name': 'Self-Consumption Warning',
        #             'type': 'ir.actions.act_window',
        #             'res_model': 'stock.picking.self.consumption.wizard',
        #             'view_mode': 'form',
        #             'view_id': False,
        #             'target': 'new',
        #             'context': {'default_picking_id': picking.id},
        #         }
        return res

    # === ACTIONS METHODS ===#

    def action_open_picking_invoice(self):
        """This is the function of the smart button which redirect to the
        invoice related to the current picking"""
        return {
            "name": _("Invoices"),
            "type": "ir.actions.act_window",
            "view_mode": "tree,form",
            "res_model": "account.move",
            "domain": [("transfer_ids", "in", self.id)],
            "context": {"create": False},
            "target": "current",
        }

    def action_create_multi_invoice_for_multi_transfer(self):
        """This is the function for creating customer invoice
        from the picking"""
        picking_type = list(self.picking_type_id)
        if all(first == picking_type[0] for first in picking_type):
            if self.picking_type_id.code == "outgoing":
                partner = list(self.partner_id)
                if all(first == partner[0] for first in partner):
                    partner_id = self.partner_id
                    invoice_line_list = []
                    customer_journal_id = self.env.company.customer_journal_id
                    if not customer_journal_id:
                        raise UserError(_("Please configure the journal from settings"))
                    for picking_id in self:
                        for (
                            move_ids_without_package
                        ) in picking_id.move_ids_without_package:
                            vals = (
                                0,
                                0,
                                {
                                    "name": move_ids_without_package.description_picking,
                                    "product_id": move_ids_without_package.product_id.id,
                                    "price_unit": move_ids_without_package.product_id.lst_price,
                                    "account_id": (
                                        move_ids_without_package.product_id.property_account_income_id.id
                                        if move_ids_without_package.product_id.property_account_income_id
                                        else move_ids_without_package.product_id.categ_id.property_account_income_categ_id.id
                                    ),
                                    "tax_ids": [
                                        (
                                            6,
                                            0,
                                            [
                                                picking_id.company_id.account_purchase_tax_id.id
                                            ],
                                        )
                                    ],
                                    "quantity": move_ids_without_package.quantity,
                                },
                            )
                            invoice_line_list.append(vals)
                    invoice = self.env["account.move"].create(
                        {
                            "move_type": "out_invoice",
                            "invoice_origin": picking_id.name,
                            "invoice_user_id": self.env.uid,
                            "narration": picking_id.name,
                            "partner_id": partner_id.id,
                            "currency_id": picking_id.env.user.company_id.currency_id.id,
                            "journal_id": int(customer_journal_id),
                            "payment_reference": picking_id.name,
                            "invoice_line_ids": invoice_line_list,
                            "transfer_ids": self,
                        }
                    )
                else:
                    for picking_id in self:
                        picking_id.create_invoice()
            elif self.picking_type_id.code == "incoming":
                partner = list(self.partner_id)
                if all(first == partner[0] for first in partner):
                    partner_id = self.partner_id
                    bill_line_list = []
                    vendor_journal_id = self.env.company.vendor_journal_id
                    if not vendor_journal_id:
                        raise UserError(
                            _("Please configure the journal from " "the settings.")
                        )
                    for picking_id in self:
                        for (
                            move_ids_without_package
                        ) in picking_id.move_ids_without_package:
                            vals = (
                                0,
                                0,
                                {
                                    "name": move_ids_without_package.description_picking,
                                    "product_id": move_ids_without_package.product_id.id,
                                    "price_unit": move_ids_without_package.product_id.lst_price,
                                    "account_id": (
                                        move_ids_without_package.product_id.property_account_income_id.id
                                        if move_ids_without_package.product_id.property_account_income_id
                                        else move_ids_without_package.product_id.categ_id.property_account_income_categ_id.id
                                    ),
                                    "tax_ids": [
                                        (
                                            6,
                                            0,
                                            [
                                                picking_id.company_id.account_purchase_tax_id.id
                                            ],
                                        )
                                    ],
                                    "quantity": move_ids_without_package.quantity,
                                },
                            )
                            bill_line_list.append(vals)
                    invoice = self.env["account.move"].create(
                        {
                            "move_type": "in_invoice",
                            "invoice_origin": picking_id.name,
                            "invoice_user_id": self.env.uid,
                            "narration": picking_id.name,
                            "partner_id": partner_id.id,
                            "currency_id": picking_id.env.user.company_id.currency_id.id,
                            "journal_id": int(vendor_journal_id),
                            "payment_reference": picking_id.name,
                            "picking_id": picking_id.id,
                            "invoice_line_ids": bill_line_list,
                            "transfer_ids": self,
                        }
                    )
                else:
                    for picking_id in self:
                        picking_id.create_bill()
        else:
            raise UserError(_("Please select single type transfer"))

    # === SEARCH METHODS ===#

    def _search_invoice_ids(self, operator, value):
        invoices = self.env["account.move"].search([("id", operator, value)])
        return [("id", "in", invoices.mapped("transfer_ids").ids)]

    # === COMPUTE METHODS ===#

    @api.depends("sale_id")
    def _compute_order_is_consignment(self):
        for picking in self:
            picking.order_is_consignment = (
                picking.sale_id.is_consignation if picking.sale_id else False
            )

    @api.depends("picking_type_id", "partner_id", "sale_id")
    def _compute_location_id(self):
        for picking in self:
            picking = picking.with_company(picking.company_id)

            if picking.picking_type_id and picking.state in ["draft", "confirmed"]:
                if picking.sale_id and picking.sale_id.is_consignation:
                    location_id = (
                        self.env["stock.location"]
                        .search(
                            [
                                ("partner_id", "=", picking.sale_id.partner_id.id),
                                ("usage", "=", "internal"),
                                ("is_consignation_warehouse", "=", True),
                            ],
                            limit=1,
                        )
                        .id
                    )
                elif picking.picking_type_id.default_location_src_id:
                    location_id = picking.picking_type_id.default_location_src_id.id
                elif picking.partner_id:
                    location_id = picking.partner_id.property_stock_supplier.id
                else:
                    _customerloc, location_id = self.env[
                        "stock.warehouse"
                    ]._get_partner_locations()

                if picking.picking_type_id.default_location_dest_id:
                    location_dest_id = (
                        picking.picking_type_id.default_location_dest_id.id
                    )
                elif picking.partner_id:
                    location_dest_id = picking.partner_id.property_stock_customer.id
                else:
                    location_dest_id, _supplierloc = self.env[
                        "stock.warehouse"
                    ]._get_partner_locations()

                picking.location_id = location_id
                picking.location_dest_id = location_dest_id

    @api.depends(
        "invoice_count", "state", "state_guide_dispatch", "operation_code", "is_return"
    )
    def _compute_button_visibility(self):
        for record in self:
            is_invoice_empty = record.invoice_count == 0
            is_done = record.state == "done"
            is_to_invoice = record.state_guide_dispatch == "to_invoice"

            record.show_create_invoice = False
            record.show_create_bill = False
            record.show_create_customer_credit = False
            record.show_create_vendor_credit = False
            record.show_create_invoice_internal = False

            if is_invoice_empty and is_done and is_to_invoice:
                if record.operation_code == "incoming":
                    record.show_create_bill = not record.is_return
                    record.show_create_vendor_credit = record.is_return

                if record.operation_code == "outgoing":
                    record.show_create_invoice = not record.is_return
                    record.show_create_customer_credit = record.is_return

                if record.operation_code == "internal" and record.is_consignment:
                    record.show_create_invoice_internal = True

    def _compute_invoice_count(self):
        for picking_id in self:
            move_ids = self.env["account.move"].search(
                [("transfer_ids", "in", picking_id.id)]
            )
            picking_id.invoice_count = len(move_ids)

    # @api.depends()
    def _compute_invoice_ids(self):
        for picking in self:
            invoices = self.env["account.move"].search(
                [("transfer_ids", "in", picking.ids)]
            )
            picking.invoice_ids = invoices

    def _compute_invoice_state(self):
        for picking_id in self:
            move_ids = picking_id.env["account.move"].search(
                [("transfer_ids", "in", picking_id.id)]
            )
            if move_ids:
                picking_id.invoice_state = move_ids[0].state
            else:
                picking_id.invoice_state = False

    @api.depends("sale_id.document")
    def _compute_has_document(self):
        for picking in self:
            picking.has_document = bool(picking.sale_id.document)

    @api.depends("is_dispatch_guide", "state", "document", "sale_id", "write_uid")
    def _compute_dispatch_guide_controls(self):
        for picking in self:
            picking.dispatch_guide_controls = False

            if picking.state != "done":
                continue

            if picking.document == "invoice":
                continue

            if picking.document == "dispatch_guide":
                picking.dispatch_guide_controls = True

            if picking.is_dispatch_guide:
                picking.dispatch_guide_controls = True

    @api.depends("sale_id")
    def _compute_show_print_button_when_is_dispatch_guide(self):
        for picking in self:
            picking.show_print_button_when_is_dispatch_guide = (
                picking.state == "done"
            ) and picking.is_dispatch_guide

    @api.depends("transfer_reason_id")
    def _compute_is_consignment(self):
        consignment_reason = self.env.ref(
            "l10n_ve_stock_account.transfer_reason_consignment",
            raise_if_not_found=False,
        )
        for picking in self:
            if consignment_reason:
                picking.is_consignment = (
                    picking.transfer_reason_id.id == consignment_reason.id
                )
            else:
                picking.is_consignment = False

    @api.depends("transfer_reason_id")
    def _compute_is_dispatch_guide(self):
        consignment_reason = self.env.ref(
            "l10n_ve_stock_account.transfer_reason_consignment",
            raise_if_not_found=False,
        )

        for picking in self:
            if (
                picking.transfer_reason_id
                and picking.transfer_reason_id.id == consignment_reason.id
            ):
                picking.is_dispatch_guide = True
            else:
                # This is necessary always should be return a value
                picking.is_dispatch_guide = picking.is_dispatch_guide

    @api.depends(
        "is_donation", "is_dispatch_guide", "operation_code", "location_dest_id"
    )
    def _compute_allowed_reason_ids(self):
        for picking in self:
            allowed_reason_ids = []

            reason_refs = {
                "donation": "l10n_ve_stock_account.transfer_reason_donation",
                "sale": "l10n_ve_stock_account.transfer_reason_sale",
                "transfer_between_warehouses": "l10n_ve_stock_account.transfer_reason_transfer_between_warehouses",
                "export": "l10n_ve_stock_account.transfer_reason_export",
                "self_consumption": "l10n_ve_stock_account.transfer_reason_self_consumption",
                "consignment": "l10n_ve_stock_account.transfer_reason_consignment",
                "repair_improvement": "l10n_ve_stock_account.transfer_reason_repair",
                "external_storage": "l10n_ve_stock_account.transfer_reason_external_storage",
                "other_causes": "l10n_ve_stock_account.transfer_reason_other_causes",
            }

            reasons = {
                key: self.env.ref(ref, raise_if_not_found=False)
                for key, ref in reason_refs.items()
            }

            is_outgoing = picking.operation_code == "outgoing"
            has_sale = bool(picking.sale_id)

            # Outgoing with sale
            if is_outgoing and has_sale:
                donation_reason = reasons.get("donation")
                sale_reason = reasons.get("sale")
                export_reason = reasons.get("export")

                # Donations
                if picking.is_donation and donation_reason:
                    allowed_reason_ids.append(donation_reason.id)
                    picking.transfer_reason_id = donation_reason.id

                # Without Donations
                else:
                    if sale_reason:
                        allowed_reason_ids.append(sale_reason.id)
                        if not picking.transfer_reason_id:
                            picking.transfer_reason_id = sale_reason.id
                    if export_reason:
                        allowed_reason_ids.append(export_reason.id)

            # Outgoing without sale
            elif is_outgoing and not has_sale:
                self_consumption_reason = reasons.get("self_consumption")
                other_causes = reasons.get("other_causes")
                repair_improvement = reasons.get("repair_improvement")
                external_storage = reasons.get("external_storage")

                if self_consumption_reason:
                    allowed_reason_ids.append(self_consumption_reason.id)
                if other_causes:
                    allowed_reason_ids.append(other_causes.id)
                if repair_improvement:
                    allowed_reason_ids.append(repair_improvement.id)
                if external_storage:
                    allowed_reason_ids.append(external_storage.id)

            # Internal
            elif picking.operation_code == "internal":

                consignment_reason = reasons.get("consignment")
                transfer_between_warehouses_reason = reasons.get(
                    "transfer_between_warehouses"
                )
                other_causes = reasons.get("other_causes")

                warehouse = picking.location_dest_id.warehouse_id

                # Consignments and internal transfers
                if consignment_reason:
                    allowed_reason_ids.append(consignment_reason.id)

                if transfer_between_warehouses_reason:
                    allowed_reason_ids.append(transfer_between_warehouses_reason.id)
                if other_causes:
                    allowed_reason_ids.append(other_causes.id)

                if (
                    consignment_reason
                    and warehouse
                    and warehouse.is_consignation_warehouse
                ):
                    picking.transfer_reason_id = consignment_reason.id
                    picking.is_consignment_readonly = True
                else:
                    picking.is_consignment_readonly = False

            # Force update of transfer_reason_id field to avoid inconsistencies
            if allowed_reason_ids:
                if picking.transfer_reason_id.id not in allowed_reason_ids:
                    picking.transfer_reason_id = allowed_reason_ids[0]

            # if not allowed_reason_ids, then return all options
            picking.allowed_reason_ids = (
                self.env["transfer.reason"].search([])
                if not allowed_reason_ids
                else self.env["transfer.reason"].search(
                    [("id", "in", allowed_reason_ids)]
                )
            )

            # if not allowed_reason_ids, then no option is returned
            # picking.allowed_reason_ids = (
            #     self.env["transfer.reason"].search([("id", "in", allowed_reason_ids)])
            #     if allowed_reason_ids
            #     else self.env["transfer.reason"]
            # )

    @api.depends('transfer_reason_id')
    def _compute_show_other_causes_transfer_reason(self):
        for record in self:
            record.show_other_causes_transfer_reason = False

            if record.transfer_reason_id:
                if record.transfer_reason_id.code == "other_causes":
                    record.show_other_causes_transfer_reason = True
                if record.transfer_reason_id.code == "self_consumption":
                    record.is_dispatch_guide = False
                else:
                    record.is_dispatch_guide = True


    # === CONSTRAINT METHODS ===#

    @api.constrains("transfer_reason_id", "operation_code")
    def _check_transfer_reason_required(self):
        for record in self:
            if record.operation_code == "internal" and not record.transfer_reason_id:
                raise ValidationError(
                    _(
                        "The 'Transfer Reason' field is mandatory when 'Operation Code' is 'internal'."
                    )
                )

    # === CRON METHODS ===#

    def _cron_generate_invoices_from_pickings(self):
        config_type = (
            self.company_id.invoice_cron_type or self.env.company.invoice_cron_type
        )
        config_time = (
            self.company_id.invoice_cron_time or self.env.company.invoice_cron_time
        )

        if self._is_execution_day(config_type) and self._is_execution_time(config_time):
            self._create_invoices_from_pickings()

    def _is_execution_day(self, config_type):
        today = fields.Date.today()
        last_day = (today.replace(day=1) + timedelta(days=32)).replace(
            day=1
        ) - timedelta(days=1)

        if config_type == "last_day":
            return today == last_day
        else:

            while last_day.weekday() >= 5:
                last_day -= timedelta(days=1)
            return today == last_day

    def _is_execution_time(self, config_time):
        current_time = datetime.now().hour + datetime.now().minute / 60
        return abs(current_time - config_time) <= 0.5

    def _create_invoices_from_pickings(self):
        pickings = self.search(
            [
                ("company_id", "=", self.env.company.id),
                ("state", "=", "done"),
                ("state_guide_dispatch", "=", "to_invoice"),
                ("invoice_count", "=", 0),
            ]
        )

        for picking in pickings:
            try:
                if all([picking.operation_code != "incoming", not picking.is_return]):
                    picking.create_invoice()

                if all([picking.operation_code != "outgoing", not picking.is_return]):
                    picking.create_bill()

                if all([picking.operation_code != "outgoing", picking.is_return]):
                    picking.create_customer_credit()

                if all([picking.operation_code != "incoming", picking.is_return]):
                    picking.create_vendor_credit()

            except Exception as e:
                _logger.error(f"Error invoicing picking {picking.name}: {str(e)}")
                picking.message_post(body=f"Error en facturación automática: {str(e)}")

    def alert_views(self):
        pickings_combined = (
            self.env["stock.picking"]
            .sudo()
            .search(
                [
                    ("state", "=", "done"),
                    ("type_delivery_step", "!=", "int"),
                    ("transfer_reason_id.code", "!=", "self_consumption"),
                    ("state_guide_dispatch", "=", "to_invoice"),
                ]
            )
        )

        hoy = date.today()
        taxpayer_type = self.env.company.taxpayer_type
        result = hoy  # Valor por defecto

        if taxpayer_type == "special":
            if hoy.day < 15:
                # Si es antes del 15: mostrar día 15
                result = hoy.replace(day=15)
            else:
                # Si es 15 o después: último día del mes
                result = date(hoy.year, hoy.month, 28) + timedelta(days=4)
                result = result - timedelta(days=1)

        elif taxpayer_type in ("ordinary", "formal"):
            # Siempre último día del mes para estos tipos
            result = date(hoy.year, hoy.month, 28) + timedelta(days=4)
            result = result - timedelta(days=1)

        return f"Tienes {len(pickings_combined)} guías de despacho sin facturar al {result.strftime('%d-%m-%Y')}. De facturarse en el siguiente periodo el Seniat será Notificado."
    
    @api.depends('is_consignment', 'is_dispatch_guide', 'transfer_reason_id')
    def _compute_partner_required(self):
        for picking in self:
            if picking.transfer_reason_id.id == self.env.ref('l10n_ve_stock_account.transfer_reason_consignment').id and picking.is_dispatch_guide and picking.is_consignment: 
                picking.partner_required = True
            else:
                picking.partner_required = False

    @api.onchange('location_dest_id', 'partner_required')
    def _change_required_partner_id(self):
        for picking in self:
            if picking.partner_required: 
                contact = self.env['res.partner'].search([('id', '=', picking.location_dest_id.partner_id.id)], limit=1)
                if contact:
                    picking.partner_id = contact.id
                else:
                    picking.partner_id = None
            else:
                picking.partner_id = None
                picking.partner_required = False
    
    def button_validate(self):
        
        for picking in self:
            if self.operation_code == 'internal' and picking.transfer_reason_id.id == self.env.ref('l10n_ve_stock_account.transfer_reason_transfer_between_warehouses').id:
                picking.state_guide_dispatch = 'emited'
        return super(StockPicking, self).button_validate()
            
