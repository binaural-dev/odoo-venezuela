from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.misc import format_datetime


class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_donation = fields.Boolean(
        string="Is Donation",
        compute="_compute_is_donation",
        readonly=False,
        tracking=True,
        store=True,
        help="Marks the picking as a donation. It is set by the Donations "
        "menu or when the picking is created from a donation sale order.",
    )
    donation_reason = fields.Char(string="Donation Reason")

    @api.depends("sale_id.is_donation")
    def _compute_is_donation(self):
        """Pickings of a donation sale order are donations. Pickings without
        a sale order keep the value they already have (the Donations menu
        sets it through `default_get`)."""
        for picking in self:
            if picking.sale_id:
                picking.is_donation = picking.sale_id.is_donation
            else:
                picking.is_donation = picking.is_donation

    @api.depends("is_donation", "sale_id")
    def _compute_button_visibility(self):
        """A donation delivery without sale order is not invoiced: the
        'Create Invoice' button would issue a regular fiscal invoice to the
        beneficiary, with no donation mark and no credit note."""
        super()._compute_button_visibility()
        for picking in self.filtered(lambda p: p.is_donation and not p.sale_id):
            picking.show_create_invoice = False

    @api.depends("is_donation")
    def _compute_match_guide_dispatch_domain(self):
        """A donation delivery has its own certificate, which replaces the
        dispatch guide: it is not listed in the dispatch guides."""
        super()._compute_match_guide_dispatch_domain()
        for picking in self.filtered("is_donation"):
            picking.match_guide_dispatch_domain = False

    @api.model
    def default_get(self, fields_list):
        """Mark the picking as a donation when it is created from the
        Donations menu.

        The menu passes `donation_menu` instead of `default_is_donation`
        because every `default_*` key of an action context is propagated to
        all the records created from it, including the stock valuation
        journal entries, which must not inherit the donation mark."""
        res = super().default_get(fields_list)
        if self.env.context.get("donation_menu") and "is_donation" in fields_list:
            res["is_donation"] = True
        elif "is_donation" in fields_list and not res.get("is_donation"):
            # A new picking opened from the card of a donation operation type
            # (the "New" button fixes `default_picking_type_id` with its type).
            picking_type = self.env["stock.picking.type"].browse(
                self.env.context.get("default_picking_type_id") or []
            ).exists()
            if picking_type.is_donation_picking_type:
                res["is_donation"] = True
        return res

    @api.depends("is_donation", "is_dispatch_guide", "operation_code", "location_dest_id")
    def _compute_allowed_reason_ids(self):
        """A donation delivery uses the 'Donation' transfer reason (the
        inventory book classifies the movement by its code). The reason is
        added to the allowed ones, not substituted: the base computation
        rewrites any reason that is not in the allowed list."""
        super()._compute_allowed_reason_ids()
        donation_reason = self._get_donation_transfer_reason()
        if not donation_reason:
            return
        for picking in self:
            if not picking._is_donation_delivery_picking():
                continue
            picking.allowed_reason_ids |= donation_reason
            if picking.transfer_reason_id != donation_reason:
                picking.transfer_reason_id = donation_reason

    @api.model
    def _get_donation_transfer_reason(self):
        return self.env.ref(
            "l10n_ve_stock_account.transfer_reason_donation", raise_if_not_found=False
        )

    def _is_donation_delivery_picking(self):
        """Outgoing donation (with or without sale order): the 'Donation'
        reason does not apply to receipts, the inventory book would count
        them as withdrawals."""
        self.ensure_one()
        return bool(self.is_donation and self.operation_code == "outgoing")

    def _assign_donation_transfer_reason(self):
        """The reason is also assigned after `create`/`write`: when the
        reason arrives in the values (the base gives each new picking the
        default reason of its operation type) the computation of the
        allowed reasons cannot overwrite it."""
        reason = self._get_donation_transfer_reason()
        if not reason:
            return
        for picking in self:
            if picking._is_donation_delivery_picking() and picking.transfer_reason_id != reason:
                picking.transfer_reason_id = reason
            if picking._is_donation_delivery_picking() and reason not in picking.allowed_reason_ids:
                picking.allowed_reason_ids |= reason

    @api.model_create_multi
    def create(self, vals_list):
        pickings = super().create(vals_list)
        pickings._assign_donation_transfer_reason()
        return pickings

    def write(self, vals):
        res = super().write(vals)
        if {"is_donation", "picking_type_id", "sale_id"} & set(vals):
            self._assign_donation_transfer_reason()
        return res

    def button_validate(self):
        for picking in self:
            if (
                picking.is_donation
                and not picking.sale_id
                and picking.picking_type_code == "outgoing"
                and not picking.partner_id
                and not picking.donation_reason
            ):
                raise UserError(_(
                    "You must set the recipient (Contact) or the donation reason "
                    "to validate a donation delivery."
                ))
            if (
                picking.is_donation
                and not picking.sale_id
                and picking.picking_type_code == "outgoing"
            ):
                errors = picking._get_donation_delivery_config_errors()
                if errors:
                    raise UserError("\n".join(errors))
            if (
                picking.is_donation
                and not picking.sale_id
                and picking.picking_type_code == "incoming"
            ):
                if not picking.partner_id:
                    raise UserError(_(
                        "You must set the donor (Receive From) to validate a donation receipt."
                    ))
                errors = picking._get_donation_receipt_config_errors()
                if errors:
                    raise UserError("\n".join(errors))
        return super().button_validate()

    def _has_real_time_valuation_moves(self):
        """Whether some non-cancelled move is of a storable product with
        automated (real_time) valuation, i.e. whether the picking generates
        valuation journal entries (the stock valuation skips the products that
        are not storable). The valuation mode is company dependent: it is read
        with the company of the picking, as the stock valuation does
        (`with_company(move.company_id)`), not with the active company of the
        user, which may differ when several companies are enabled."""
        self.ensure_one()
        products = self.move_ids.filtered(
            lambda move: move.state != "cancel"
        ).product_id.with_company(self.company_id)
        return any(
            product.is_storable and product.valuation == "real_time"
            for product in products
        )

    def _get_donation_delivery_config_errors(self):
        """Return the list of messages describing why the configuration of
        this donation delivery is not coherent (empty if it is).

        The valuation journal entry of the delivery is determined by the
        configuration, not forced by the donation hook: the stock valuation
        takes the debit account from the destination location, which must be
        an `inventory` location. Its valuation account is required only when
        a move has a product with automated (real_time) valuation: otherwise
        the delivery generates no valuation entry. Extension point: other
        modules append their own checks with `super()`."""
        self.ensure_one()
        errors = []
        moves = self.move_ids.filtered(lambda move: move.state != "cancel")
        locations = self.location_dest_id | moves.location_dest_id
        is_real_time = self._has_real_time_valuation_moves()
        for location in locations:
            if location.usage != "inventory":
                # The account of a location that is not a donation destination
                # is not evaluated: the destination itself must be changed.
                errors.append(_(
                    "The destination %(location)s of a donation delivery is not of type "
                    "Inventory Loss. Change the Destination Location of the delivery (or the "
                    "Default Destination Location of its operation type) to an Inventory Loss "
                    "location, e.g. the default destination of the donation operation type.",
                    location=location.display_name,
                ))
            elif is_real_time and not location.valuation_account_id:
                errors.append(_(
                    "The destination location %(location)s of a donation delivery has no "
                    "Stock Valuation Account. Set it in Inventory > Configuration > "
                    "Locations, in the Accounting Information section of the location.",
                    location=location.display_name,
                ))
            elif is_real_time and location.valuation_account_id in self.company_id.donation_income_account_ids:
                errors.append(_(
                    "The Stock Valuation Account %(account)s of the destination location "
                    "%(location)s is a received donations account: a donation delivery cannot "
                    "use it. Use as destination the location of the donations given (an "
                    "Inventory Loss location whose Stock Valuation Account is the donation "
                    "expense account).",
                    account=location.valuation_account_id.display_name,
                    location=location.display_name,
                ))
        return errors

    def _get_donation_receipt_config_errors(self):
        """Return the list of messages describing why the configuration of
        this donation receipt is not coherent (empty if it is).

        The valuation journal entry of the receipt is determined by the
        configuration: when the origin location has a valuation account the
        stock valuation credits it, so the origin must be an `inventory`
        location whose account is one of the received donations accounts of
        the company, which is what identifies the income of the donation.
        Only required when a move has a product with automated (real_time)
        valuation: otherwise the receipt generates no valuation entry.
        Extension point: other modules append their own checks with
        `super()`."""
        self.ensure_one()
        errors = []
        if not self._has_real_time_valuation_moves():
            return errors
        income_accounts = self.company_id.donation_income_account_ids
        if not income_accounts:
            errors.append(_(
                "The company %(company)s has no received donations accounts configured. Set "
                "them in the settings of the company (Received Donations Accounts).",
                company=self.company_id.display_name,
            ))
        moves = self.move_ids.filtered(lambda move: move.state != "cancel")
        for location in self.location_id | moves.location_id:
            if location.usage != "inventory":
                # The account of a location that is not an inventory one is
                # not evaluated: the origin itself must be changed.
                errors.append(_(
                    "The origin %(location)s of a donation receipt must be an Inventory Loss "
                    "location, e.g. \"Donations received\". Change the origin of the receipt.",
                    location=location.display_name,
                ))
            elif not location.valuation_account_id:
                errors.append(_(
                    "The origin %(location)s of a donation receipt has no Stock Valuation "
                    "Account. Use as origin a received donations location (Inventory Loss) and "
                    "set its Stock Valuation Account with one of the received donations "
                    "accounts (%(accounts)s), in Inventory > Configuration > Locations.",
                    location=location.display_name,
                    accounts=", ".join(income_accounts.mapped("display_name")),
                ))
            elif income_accounts and location.valuation_account_id not in income_accounts:
                errors.append(_(
                    "The Stock Valuation Account %(account)s of the origin %(location)s is not a "
                    "received donations account. Set one of them (%(accounts)s) in Inventory > "
                    "Configuration > Locations.",
                    account=location.valuation_account_id.display_name,
                    location=location.display_name,
                    accounts=", ".join(income_accounts.mapped("display_name")),
                ))
        return errors

    def _get_donation_product_lines(self):
        """Per-line detail (code, description, qty, uom, lot, expiration,
        cost) -- from the value stored in the stock move
        (`stock.move.value`), not `product_id.standard_price`, so reprinting
        always gives the same number.

        `expiration_date` is resolved here (not in the shared report
        sub-template): `stock.lot.expiration_date` only exists when
        `product_expiry` is installed, an optional dependency this module
        does not require. It is formatted with `format_datetime` (user's
        language/timezone), with `dt_format=False` so it uses the user's
        language date/time format -- same style `t-field` would use
        elsewhere in this same document -- rather than left as a raw
        datetime; the shared template only does `t-out` on the
        already-resolved value, not `t-field`."""
        self.ensure_one()
        data = []
        for line in self.move_line_ids:
            move = line.move_id
            valued_qty = move._get_valued_qty() if move.state == "done" else 0.0
            unit_cost = abs(move.value / valued_qty) if valued_qty else 0.0
            expiration_date = (
                format_datetime(self.env, line.lot_id.expiration_date, dt_format=False)
                if line.lot_id and "expiration_date" in line.lot_id._fields and line.lot_id.expiration_date
                else False
            )
            data.append({
                "line": line,
                "unit_cost": unit_cost,
                "total_value": unit_cost * line.quantity_product_uom,
                "expiration_date": expiration_date,
            })
        return data

    def _get_donation_grand_total(self):
        self.ensure_one()
        return sum(row["total_value"] for row in self._get_donation_product_lines())

    def _get_donation_receipt_amounts(self):
        """Amounts of the receipt of a delivery: the cost of the goods (see
        `_get_donation_grand_total`) and, when its valuation entries have an
        alternate amount, its equivalent at the rate of the entry, so that a
        reprint always gives the same numbers."""
        self.ensure_one()
        entries = self.move_ids.account_move_id.filtered(lambda entry: entry.state == "posted")
        entry = entries[:1]
        return self.env["account.move"]._compute_donation_amounts(
            self.company_id.currency_id,
            entry.foreign_currency_id,
            self._get_donation_grand_total(),
            sum(entries.mapped("foreign_debit")),
            entry.foreign_rate,
            entry.foreign_inverse_rate,
        )

    def _get_donation_beneficiary(self):
        self.ensure_one()
        return self.partner_id

    def _get_donation_document_date(self):
        """Local date of the document: the date it was done."""
        self.ensure_one()
        return fields.Date.context_today(self, self.date_done or self.scheduled_date)

    def print_donation_certificate(self):
        """The certificate of a donation receipt (goods), delivered to the
        donor."""
        self.ensure_one()
        if not (self.is_donation and not self.sale_id and self.picking_type_code == "incoming"):
            raise UserError(_(
                "This picking is not a donation receipt: only those have a Donation "
                "Certificate. A donation delivery has a Donation Receipt."
            ))
        return self.env.ref("l10n_ve_donation.action_donation_certificate_stock_picking").report_action(self)

    def print_donation_receipt(self):
        self.ensure_one()
        if self.picking_type_code == "incoming":
            raise UserError(_(
                "This picking is a donation receipt: its document is the Donation Certificate."
            ))
        return self.env.ref("l10n_ve_donation.action_donation_receipt_stock_picking").report_action(self)
