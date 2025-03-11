import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from datetime import datetime, timedelta

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

    show_create_invoice = fields.Boolean(compute="_compute_button_visibility")
    show_create_bill = fields.Boolean(compute="_compute_button_visibility")
    show_create_customer_credit = fields.Boolean(compute="_compute_button_visibility")
    show_create_vendor_credit = fields.Boolean(compute="_compute_button_visibility")

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

    allowed_reason_ids = fields.Many2many(
        "transfer.reason",
        string="Allowed Reasons",
        store=True,
        compute="_compute_allowed_reason_ids",
    )

    is_donation = fields.Boolean(related="sale_id.is_donation")

    is_dispatch_guide = fields.Boolean(
        string="Is Dispatch Guide",
        default=False,
        tracking=True,
        store=True,
        compute="_compute_is_dispatch_guide",
    )

    is_consignment = fields.Boolean(compute="_compute_is_consignment", store=True)

    # This field controls the visibility of the button, determines when to generate 
    # the dispatch guide sequence, and controls the visibility of the 'guide_number' field.
    dispatch_guide_controls = fields.Boolean(
        compute="_compute_dispatch_guide_controls", store=True
    )

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
            raise UserError(
                _("You cannot create an invoice from this picking for this state.")
            )

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
            if picking_id.picking_type_id.code == "outgoing":
                customer_journal_id = (
                    picking_id.env["ir.config_parameter"]
                    .sudo()
                    .get_param("stock_move_invoice.customer_journal_id")
                    or False
                )
                if not customer_journal_id:
                    raise UserError(_("Please configure the journal from settings"))

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
            picking_id.write({"state_guide_dispatch": "invoiced"})
        return True 

    def _get_invoice_lines_for_invoice(self):
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
                    "quantity": move_id.quantity_done,
                },
            )
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

        res = self.company_id.currency_foreign_id == self.env.ref("base.VEF")

        _logger.info("Is VEF: %s", res)

        return res

    def get_digits(self):
        return self.env.ref("base.VEF").decimal_places

    def get_totals(self, use_foreign_currency=False):
        """Calcula y agrupa los totales del picking, incluyendo impuestos por porcentaje."""
        self.ensure_one()
        totals = {
            "subtotal": 0.0,   # Suma de todos los subtotales
            "exempt": 0.0,     # Suma de productos exentos (0% IVA)
            "tax_base": 0.0,   # Base imponible (productos con IVA)
            "tax": 0.0,        # Total de impuestos calculados
            "total": 0.0,      # Monto final correcto
            "tax_details": {}, # Agrupación de impuestos por porcentaje
        }

        for line in self.move_ids_without_package:
            line_values = line._get_line_values(use_foreign_currency=use_foreign_currency)
            
            totals["subtotal"] += line_values["subtotal_after_discount"]
            
            tax_rate = line_values["tax_percentage"]
            tax_amount = line_values["tax_amount"]
            subtotal_after_discount = line_values["subtotal_after_discount"]

            # Si es exento (0%), solo lo sumamos a "exempt"
            if tax_rate == 0.0:
                totals["exempt"] += subtotal_after_discount
            else:
                totals["tax_base"] += subtotal_after_discount
                totals["tax"] += tax_amount

                # Agrupar impuestos por porcentaje
                if tax_rate not in totals["tax_details"]:
                    totals["tax_details"][tax_rate] = {
                        "base": 0.0,
                        "tax_amount": 0.0,
                    }
                
                totals["tax_details"][tax_rate]["base"] += subtotal_after_discount
                totals["tax_details"][tax_rate]["tax_amount"] += tax_amount

        totals["total"] = totals["exempt"] + totals["tax_base"] + totals["tax"]

        return totals

    def create_bill(self):
        self._validate_one_invoice_posted()
        res = super().create_bill()
        for picking in self:
            picking.write({"state_guide_dispatch": "invoiced"})
        return res

    
    def create_customer_credit(self):
        self._validate_one_invoice_posted()
        res = super().create_customer_credit()
        for picking in self:
            picking.write({"state_guide_dispatch": "invoiced"})
        return res
    
    def create_vendor_credit(self):
        self._validate_one_invoice_posted()
        res = super().create_vendor_credit()
        for picking in self:
            picking.write({"state_guide_dispatch": "invoiced"})
        return res
    
    def _validate_one_invoice_posted(self):
        for picking in self:
            invoice_ids = self.env["account.move"].search(
                [("picking_id", "=", picking.id), ("state", "=", "posted")]
            )
            if invoice_ids:
                raise UserError(
                    _(
                        "This guide has at least one posted invoice, please check your invoice."
                    )
                )
            
    def _get_origin_name(self, picking):
        if picking.operation_code == 'outgoing':
            if picking.sale_id:
                return picking.sale_id.name
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

    #=== COMPUTE METHODS ===#

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

            if not picking.sale_id:
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

    @api.depends("is_donation", "is_dispatch_guide", "operation_code")
    def _compute_allowed_reason_ids(self):
        for picking in self:
            allowed_reason_ids = []

            reason_refs = {
                "donation": "l10n_ve_stock_account.transfer_reason_donation",
                "consignment": "l10n_ve_stock_account.transfer_reason_consignment",
                "internal": "l10n_ve_stock_account.transfer_reason_internal_transfer",
                "self_consumption": "l10n_ve_stock_account.transfer_reason_self_consumption",
            }

            reasons = {key: self.env.ref(ref, raise_if_not_found=False) for key, ref in reason_refs.items()}

            # Donations
            if picking.is_donation and reasons["donation"]:
                allowed_reason_ids.append(reasons["donation"].id)
                picking.transfer_reason_id = reasons["donation"].id

            # Consignments and internal transfers
            elif picking.operation_code == "internal":
                if reasons["consignment"]:
                    allowed_reason_ids.append(reasons["consignment"].id)
                if reasons["internal"]:
                    allowed_reason_ids.append(reasons["internal"].id)

            # Self Consumption
            elif picking.operation_code == "outgoing" and reasons["self_consumption"]:
                allowed_reason_ids.append(reasons["self_consumption"].id)

            picking.transfer_reason_id = allowed_reason_ids[0] if allowed_reason_ids else False

            picking.allowed_reason_ids = (
                self.env["transfer.reason"].search([("id", "in", allowed_reason_ids)])
                if allowed_reason_ids
                else self.env["transfer.reason"]
            )

    #=== CONSTRAINT METHODS ===#

    @api.constrains("transfer_reason_id", "write_uid")
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
        config_type = self.company_id.invoice_cron_type or self.env.company.invoice_cron_type
        config_time = self.company_id.invoice_cron_time or self.env.company.invoice_cron_time

        if self._is_execution_day(config_type) and self._is_execution_time(config_time):
            self._create_invoices_from_pickings()

    def _is_execution_day(self, config_type):
        today = fields.Date.today()
        last_day = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)

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

                picking.write({"state_guide_dispatch": "invoiced"})

            except Exception as e:
                _logger.error(f"Error invoicing picking {picking.name}: {str(e)}")
                picking.message_post(body=f"Error en facturación automática: {str(e)}")
