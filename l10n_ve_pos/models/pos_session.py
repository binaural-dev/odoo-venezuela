from odoo import models, fields, api, _, Command
from odoo.tools import float_is_zero, float_compare
from odoo.osv.expression import AND, OR
from odoo.exceptions import ValidationError
import logging
import math

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = "pos.session"

    foreign_currency_id = fields.Many2one(
        "res.currency",
        related="config_id.foreign_currency_id",
        string="Foreign Currency",
    )

    def load_pos_data(self):
        res = super().load_pos_data()
        res["prefix_vats"] = self.env["res.partner"]._fields["prefix_vat"].selection
        return res

    def _loader_params_pos_payment(self):
        res = super()._loader_params_pos_payment(self)
        res["search_params"]["fields"].append("foreign_rate")
        return res

    def _loader_params_pos_payment_method(self):
        res = super()._loader_params_pos_payment_method()
        res["search_params"]["fields"].append("is_foreign_currency")
        return res

    def _loader_params_account_tax(self):
        res = super()._loader_params_account_tax()
        res["search_params"]["fields"].append("type_tax_use")
        return res

    def _loader_params_res_partner(self):
        res = super()._loader_params_res_partner()
        res["search_params"]["fields"].append("prefix_vat")
        res["search_params"]["fields"].append("city_id")
        return res

    def _loader_params_res_currency(self):
        """
        This method is used to get the params for the search_read of res.currency
        """
        res = super()._loader_params_res_currency()
        res["search_params"]["domain"] = [
            ("id", "in", [self.config_id.currency_id.id, self.config_id.foreign_currency_id.id])
        ]
        res["search_params"]["fields"].append("inverse_rate")
        return res

    def _loader_params_product_product(self):
        params = super()._loader_params_product_product()
        params["search_params"]["fields"].append("free_qty")
        params["search_params"]["fields"].append("qty_available")
        params["context"] = {
            **params["context"],
            "warehouse": self.config_id.picking_type_id.warehouse_id.id,
        }
        return params

    def _loader_params_res_company(self):
        return {
            'search_params': {
                'domain': [('id', '=', self.company_id.id)],
                'fields': [
                    'currency_id', 'email', 'street', 'website', 'company_registry', 'vat', 'name', 'phone', 'partner_id',
                    'country_id', 'state_id', 'tax_calculation_rounding_method', 'nomenclature_id', 'point_of_sale_use_ticket_qr_code',
                    'point_of_sale_ticket_unique_code', 'account_fiscal_country_id',
                ],
            }
        }
    #TODO fue comentado por Omar, por lo tanto necesito aclaratoria o analisis de AI
    def _get_pos_ui_product_product(self, params):
        self = self.with_context(**params["context"])
        products = []
        if not self.config_id.limited_products_loading:
            products = self.env["product.product"].search_read(**params["search_params"])
        else:
            products = self.config_id.get_limited_products_loading(
                params["search_params"]["fields"]
            )

        products = self._sort_available_products(products)
        self._process_pos_ui_product_product(products)
        return products

    def _loader_params_res_country_city(self):
        return {"search_params": {"domain": [], "fields": ["name", "id"]}}

    def _get_pos_ui_res_country_city(self, params):
        return self.env["res.country.city"].search_read(**params["search_params"])

    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        if "res.country.city" not in result:
            result.append("res.country.city")
        return result

    def get_pos_ui_product_product_by_params(self, custom_search_params):
        """
        :param custom_search_params: a dictionary containing params of a search_read()
        """
        params = self._loader_params_product_product()
        self = self.with_context(**params['context'])
        # custom_search_params will take priority
        params["search_params"] = {**params["search_params"], **custom_search_params}
        products = (
            self.env["product.product"]
            .with_context(active_test=False)
            .search_read(**params["search_params"])
        )
        products = self._sort_available_products(products)
        if len(products) > 0:
            self._process_pos_ui_product_product(products)
        return products

    def _sort_available_products(self, products):
        if not self.env.company.pos_show_just_products_with_available_qty:
            return products

        return sorted(products, key=lambda x: x["qty_available"], reverse=True)

    def _get_pos_ui_res_currency(self, params):
        """
        This method is used to get the res.currency for the pos
        is override to change the order of the currencies
        ------
        Return:
        Array:
            0: company currency
            1: foreign currency
        """
        res = self.env["res.currency"].search_read(**params["search_params"])
        if res[0]["id"] != self.config_id.currency_id.id:
            return [res[1], res[0]]
        return res

    def is_user_authorized(self):
        is_group = self.env.user.has_group("l10_ve_pos.group_authorized_discount_pos")
        return is_group

    def _validate_cross_move(self):
        """This function validate cross move, the proposal of this function is the transitory account be zero"""
        for session in self:
            for order_payment in session.order_ids.payment_ids:
                if not order_payment.payment_method_id.apply_one_cross_move:
                    if (
                        order_payment.payment_method_id.cross_account_journal
                        and order_payment.payment_method_id.cross_journal
                    ):

                        if order_payment.amount < 0:
                            line_vals = session._line_vals_move_cross_outgoing(order_payment)
                        else:
                            line_vals = session._line_vals_move_cross_incoming(order_payment)

                        session._create_cross_move(order_payment, line_vals)

    def _line_vals_move_cross_incoming(self, payment):
        """
        This method creates the move_lines for the move_cross when the payment is incoming.

        Args:
            payment (account.payment): payment generate from PoS

        Returns:
            account.move.line: move line to move cross
        """
        credit_account = 0
        debit_account = 0
        move_lines = []
        for account in payment.payment_method_id:
            debit_account = account.outstanding_account_id.id

        for account_method in payment.payment_method_id.cross_journal:
            credit_account = account_method.inbound_payment_method_line_ids.payment_account_id.id
            currency = (
                account_method.currency_id.id
                if account_method.currency_id
                else self.env.company.currency_id.id
            )

            move_lines.extend(
                [
                    Command.create(
                        {
                            "name": _("PoS Payment Method Adjustment"),
                            "account_id": credit_account,
                            "partner_id": payment.partner_id.id,
                            "amount_currency": payment.foreign_amount
                            if currency == 3
                            else payment.amount,
                            "credit": 0.0,
                            "foreign_credit": 0.0,
                            "debit": payment.amount,
                            "foreign_debit": payment.foreign_amount,
                            "not_foreign_recalculate": True,
                            "foreign_rate": payment.foreign_rate,
                            "currency_id": account_method.currency_id.id
                            if account_method.currency_id
                            else self.env.company.currency_id.id,
                        }
                    ),
                    Command.create(
                        {
                            "name": _("PoS Payment Method Adjustment"),
                            "account_id": debit_account,
                            "partner_id": payment.partner_id.id,
                            "amount_currency": -payment.foreign_amount
                            if self.env.company.currency_id.id == 3
                            else -payment.amount,
                            "debit": 0.0,
                            "foreign_debit": 0.0,
                            "credit": payment.amount,
                            "foreign_credit": payment.foreign_amount,
                            "not_foreign_recalculate": True,
                            "foreign_rate": payment.foreign_rate,
                            "currency_id": self.env.company.currency_id.id,
                        }
                    ),
                ]
            )

            return move_lines

    def _line_vals_move_cross_outgoing(self, payment):
        """
        This method creates the move_lines for the move_cross when the payment is outgoing (is change).

        Args:
            payment (pos.payment): payment generate from PoS

        Returns:
            account.move.line: move line to move cross
        """
        credit_account = 0
        debit_account = 0
        move_lines = []

        for account in payment.payment_method_id:
            debit_account = account.outstanding_account_id.id

        for account_method in payment.payment_method_id.cross_journal:
            credit_account = account_method.outbound_payment_method_line_ids.payment_account_id.id
            currency = (
                account_method.currency_id.id
                if account_method.currency_id
                else self.env.company.currency_id.id
            )
            move_lines.extend(
                [
                    Command.create(
                        {
                            "name": _("PoS Payment Method Adjustment"),
                            "account_id": debit_account,
                            "partner_id": payment.partner_id.id,
                            "amount_currency": abs(payment.foreign_amount)
                            if self.env.company.currency_id.id == 3
                            else abs(payment.amount),
                            "credit": 0.0,
                            "foreign_credit": 0.0,
                            "debit": abs(payment.amount),
                            "foreign_debit": abs(payment.foreign_amount),
                            "not_foreign_recalculate": True,
                            "foreign_rate": payment.foreign_rate,
                            "currency_id": self.env.company.currency_id.id,
                        }
                    ),
                    Command.create(
                        {
                            "name": _("PoS Payment Method Adjustment"),
                            "account_id": credit_account,
                            "partner_id": payment.partner_id.id,
                            "amount_currency": payment.foreign_amount
                            if currency == 3
                            else payment.amount,
                            "debit": 0.0,
                            "foreign_debit": 0.0,
                            "credit": abs(payment.amount),
                            "foreign_credit": abs(payment.foreign_amount),
                            "not_foreign_recalculate": True,
                            "foreign_rate": payment.foreign_rate,
                            "currency_id": account_method.currency_id.id
                            if account_method.currency_id
                            else self.env.company.currency_id.id,
                        }
                    ),
                ]
            )

            return move_lines

    def _get_pos_ui_product_category(self, params):
        categories = self.env['product.category'].search_read(**params['search_params'])
        category_by_id = {category['id']: category for category in categories}

        for category in categories:
            try:
                category['parent'] = category_by_id[category['parent_id'][0]] if category['parent_id'] else None
            except KeyError as e:
                raise ValueError(_(f"The category %s does not belong to this company.") % category['parent_id'][1]) from e

        return categories

    def _process_pos_ui_product_product(self, products):
        """
        Modify the list of products to add the categories as well as adapt the lst_price
        :param products: a list of products
        """
        if self.config_id.currency_id != self.company_id.currency_id:
            for product in products:
                product['lst_price'] = self.company_id.currency_id._convert(
                    product['lst_price'],
                    self.config_id.currency_id,
                    self.company_id,
                    fields.Date.today()
                )

        categories = self._get_pos_ui_product_category(self._loader_params_product_category())
        product_category_by_id = {category['id']: category for category in categories}

        for product in products:
            categ_id = product['categ_id'][0]
            if categ_id in product_category_by_id:
                product['categ'] = product_category_by_id[categ_id]
            else:
                raise ValueError(_(f"The category %s does not belong to this company.") % product['categ_id'][1])

            product['image_128'] = bool(product['image_128'])

    def _create_cross_move(self, payment, line_vals):
        """
         This method create the move for the transitory account sets zero.

        Args:
            payment (pos.payment): payment from PoS
            line_vals (account.move.line): move line to move cross

        Returns:
            account.move: Pos payment method adjustment move.
        """

        move = self.env["account.move"].create(
            {
                "name": _("PoS Payment Method Adjustment"),
                "date": payment.create_date,
                "journal_id": payment.payment_method_id.cross_account_journal.id,
                "state": "draft",
                "line_ids": line_vals,
                "foreign_currency_id": payment.foreign_currency_id.id,
                "foreign_rate": payment.foreign_rate,
                "company_id": self.company_id.id,
            }
        )
        return move #TODO esta funcion no hace nada, esta definida y no me explico como es que no

    def action_pos_session_close(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        """
        Keep Odoo's standard close flow without mutating order totals afterwards.
        """
        return super().action_pos_session_close(
            balancing_account,
            amount_to_balance,
            bank_payment_method_diffs,
        )

    def _apply_rounding(self, amount):
        """ Aplica el redondeo a dos decimales (ajusta según la moneda) """
        return round(amount, 2)

    def _handle_refund(self, order):
        """ Maneja los reembolsos para asegurarse de que los impuestos no se apliquen nuevamente """
        for line in order.lines:
            # Verifica si la línea tiene un impuesto que no debería aplicarse nuevamente
            if line.tax_ids:
                for tax in line.tax_ids:
                    if tax.name == "IGTF":
                        _logger.info(f"log_tax_after {tax.name}")  # Ajusta al nombre de tu impuesto IGTF
                        # Asegúrate de que el impuesto no se aplique nuevamente en el reembolso
                        line.price_subtotal = self._apply_rounding(line.price_subtotal / (1 + (tax.amount / 100)))
                        line.price_total = self._apply_rounding(line.price_total / (1 + (tax.amount / 100)))

    def _create_combine_account_payment(self, payment_method, amounts, diff_amount):
        res = super(PosSession, self.with_context(from_pos=False))._create_combine_account_payment(
            payment_method, amounts, diff_amount
        )

        # res ya es el objeto account.payment en esta versión
        account_payment = res
        account_payment.write(
            {
                "foreign_rate": self.config_id.foreign_rate,
                "foreign_inverse_rate": self.config_id.foreign_inverse_rate,
            }
        )
        for line in account_payment.move_id.line_ids:
            if line.credit > 0:
                line.not_foreign_recalculate = True
                line.foreign_credit = line.credit / self.config_id.foreign_rate
                _logger.warning(f"LINE CREDIT: {line.credit} - FOREIGN CREDIT: {line.foreign_credit}")

            if line.debit > 0:
                line.not_foreign_recalculate = True
                line.foreign_debit = line.debit / self.config_id.foreign_rate
                _logger.warning(f"LINE DEBIT: {line.debit} - FOREIGN DEBIT: {line.foreign_debit}")
        # raise ValidationError("XD")
        return res

    def _create_cross_move_payment(self, move):
        super()._create_cross_move_payment(move)
        move = self.env["account.move"].create(
            {
                "name": _("PoS Payment Method Adjustment"),
                "date": move.move_id.create_date,
                "journal_id": move.move_id.payment_id.pos_payment_method_id.cross_account_journal.id,
                "state": "draft",
                "line_ids": self._line_vals_move_cross_payment_incoming(move),
                "foreign_currency_id": move.move_id.foreign_currency_id.id,
                "foreign_rate": move.move_id.foreign_rate,
                "company_id": self.company_id.id,
            }
        )
        return move

    def _line_vals_move_cross_payment_incoming(self, move):
        """
        This method creates the move_lines for the move_cross when the payment is incoming.

        Args:
            payment (account.payment): payment generate from PoS

        Returns:
            account.move.line: move line to move cross
        """
        credit_account = 0
        debit_account = 0
        move_lines = []
        for account in move.move_id.payment_id.pos_payment_method_id:
            debit_account = account.outstanding_account_id.id

        for account_method in move.move_id.payment_id.pos_payment_method_id.cross_journal:
            credit_account = account_method.inbound_payment_method_line_ids.payment_account_id.id
            currency = (
                account_method.currency_id.id
                if account_method.currency_id
                else self.env.company.currency_id.id
            )

            move_lines.extend(
                [
                    Command.create(
                        {
                            "name": _("PoS Payment Method Adjustment"),
                            "account_id": credit_account,
                            "amount_currency": abs(move.foreign_credit)
                            if currency == 3
                            else abs(move.credit),
                            "credit": 0.0,
                            "foreign_credit": 0.0,
                            "debit": abs(move.credit),
                            "foreign_debit": abs(move.foreign_credit),
                            "not_foreign_recalculate": True,
                            "foreign_rate": move.move_id.payment_id.foreign_inverse_rate,
                            "currency_id": account_method.currency_id.id
                            if account_method.currency_id
                            else self.env.company.currency_id.id,
                        }
                    ),
                    Command.create(
                        {
                            "name": _("PoS Payment Method Adjustment"),
                            "account_id": debit_account,
                            "amount_currency": -move.foreign_credit
                            if self.env.company.currency_id.id == 3
                            else -move.credit,
                            "debit": 0.0,
                            "foreign_debit": 0.0,
                            "credit": abs(move.credit),
                            "foreign_credit": abs(move.foreign_credit),
                            "not_foreign_recalculate": True,
                            "foreign_rate": move.move_id.payment_id.foreign_rate,
                            "currency_id": self.env.company.currency_id.id,
                        }
                    ),
                ]

            )

            return move_lines

    def _create_account_move(
        self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None
    ):
        """
        Ensure POS closing move carries the configured foreign rates so tax lines
        can compute foreign debit/credit consistently.
        """
        res = super()._create_account_move(
            balancing_account,
            amount_to_balance,
            bank_payment_method_diffs,
        )
        self.move_id.write(
            {
                "foreign_rate": self.config_id.foreign_rate,
                "foreign_inverse_rate": self.config_id.foreign_inverse_rate,
                "manually_set_rate": True,
            }
        )
        return res

    def _accumulate_amounts(self, data):
        """
        Acumula los montos de pagos del POS para el cierre contable de la sesión,
        extendiendo la lógica base para incluir también montos en moneda extranjera
        (`foreign_amount`).

        Propósito:
            - Consolidar importes de pagos por tipo de método de pago (efectivo/banco).
            - Separar la acumulación según configuración del método:
              * pagos divididos (`split_transactions=True`) por pago individual,
              * pagos combinados (`split_transactions=False`) por método de pago.
            - Mantener la lógica de cuentas por cobrar de facturas (`order.is_invoiced`)
              con acumulación específica para conciliación, donde el `amount` local se
              deja en 0 y se acumula el `foreign_amount`.

        Funcionamiento general:
            1. Ejecuta primero la implementación padre para conservar acumulados estándar.
            2. Obtiene de `data` las estructuras de acumulación (split/combine, cash/bank,
               e invoice receivables).
            3. Recorre órdenes y pagos de la sesión, omitiendo pagos con monto local cero
               (según redondeo de la moneda de la sesión).
            4. Según tipo de pago y modo split/combine, actualiza el bucket
               correspondiente mediante `_update_amounts`, agregando:
               - `amount` (moneda de la sesión)
               - `foreign_amount` (moneda extranjera)
            5. Si la orden está facturada, actualiza además los acumulados de
               receivables de factura para balancear los asientos de pagos de facturas.
            6. Reinyecta en `data` los diccionarios actualizados y retorna el resultado.

        Args:
            data (dict): Estructura acumuladora heredada del método padre con los
                contenedores de receivables y metadata de agregación.

        Returns:
            dict: El mismo diccionario `data` con acumulados actualizados, incluyendo
            importes locales y en moneda extranjera para cada categoría de receivable.
        """
        data = super()._accumulate_amounts(data)

        split_receivables_bank = data.get("split_receivables_bank")
        split_receivables_cash = data.get("split_receivables_cash")
        combine_receivables_bank = data.get("combine_receivables_bank")
        combine_receivables_cash = data.get("combine_receivables_cash")
        combine_invoice_receivables = data.get("combine_invoice_receivables")
        split_invoice_receivables = data.get("split_invoice_receivables")

        def _add_foreign_amount(bucket, key, value):
            values = bucket.get(key)
            if values is None:
                values = {"amount": 0.0, "amount_converted": 0.0}
            _logger.warning("VALUES BEFORE ADDING FOREIGN AMOUNT %s", values)
            values["foreign_amount"] = values.get("foreign_amount", 0.0) + value
            _logger.warning("VALUES AFTER ADDING FOREIGN AMOUNT %s", values)
            bucket[key] = values

        _logger.warning("DATA EN _ACCUMULATE_AMOUNTS %s", data)

        currency_rounding = self.currency_id.rounding
        for order in self.order_ids:
            order_is_invoiced = order.is_invoiced
            for payment in order.payment_ids:
                amount = payment.amount
                foreign_amount = payment.foreign_amount
                if float_is_zero(amount, precision_rounding=currency_rounding) and float_is_zero(
                    foreign_amount,
                    precision_rounding=currency_rounding,
                ):
                    continue
                payment_method = payment.payment_method_id
                is_split_payment = payment.payment_method_id.split_transactions
                payment_type = payment_method.type

                if payment_type != "pay_later":
                    if is_split_payment and payment_type == "cash":

                        _add_foreign_amount(
                            split_receivables_cash,
                            payment,
                            foreign_amount,
                        )
                    elif not is_split_payment and payment_type == "cash":
                        _add_foreign_amount(
                            combine_receivables_cash,
                            payment_method,
                            foreign_amount,
                        )
                    #no es un pago completo
                    elif is_split_payment and payment_type == "bank":
                        _add_foreign_amount(
                            split_receivables_bank,
                            payment,
                            foreign_amount,
                        )
                    #es un pago completo
                    elif not is_split_payment and payment_type == "bank":
                        _add_foreign_amount(
                            combine_receivables_bank,
                            payment_method,
                            foreign_amount,
                        )

                    # Create the vals to create the pos receivables that will balance the pos receivables from invoice payment moves.
                    if order_is_invoiced:
                        if is_split_payment:
                            _add_foreign_amount(
                                split_invoice_receivables,
                                payment,
                                payment.foreign_amount,
                            )
                        else:
                            _add_foreign_amount(
                                combine_invoice_receivables,
                                payment_method,
                                payment.foreign_amount,
                            )

        data.update(
            {
                "split_receivables_cash": split_receivables_cash,
                "combine_receivables_cash": combine_receivables_cash,
                "split_receivables_bank": split_receivables_bank,
                "combine_receivables_bank": combine_receivables_bank,
                "combine_invoice_receivables": combine_invoice_receivables,
                "split_invoice_receivables": split_invoice_receivables,
            }
        )
        # raise ValidationError(_("The session cannot be closed because the payment %s has amount %s and foreign amount %s. Please, review the payments of the session.") % (payment.id, amount, foreign_amount))
        return data

    def _update_amounts(
        self, old_amounts, amounts_to_add, date, round=True, force_company_currency=False
    ):
        
        new_amounts = super()._update_amounts(
            old_amounts, amounts_to_add, date, round, force_company_currency
        )
        foreign_amount = amounts_to_add.get("foreign_amount", 0)
        new_amounts.update(
            {"foreign_amount": old_amounts.get("foreign_amount", 0) + foreign_amount}
        )
        return new_amounts

    def _create_invoice_receivable_lines(self, data):
        """ This method is used to create the invoice receivable lines, is override to set the foreign amounts in the move lines of the invoice receivables."""
        res = super()._create_invoice_receivable_lines(data)
        combine_invoice_receivable_lines = res.get("combine_invoice_receivable_lines")
        split_invoice_receivable_lines = res.get("split_invoice_receivable_lines")
        combine_invoice_receivables = res.get("combine_invoice_receivables")
        for payment_method, amounts in combine_invoice_receivables.items():
            line = combine_invoice_receivable_lines[payment_method]

            if line.credit > 0:
                line.not_foreign_recalculate = True
                line.foreign_credit = line.credit / self.config_id.foreign_rate

            if line.debit > 0:
                line.not_foreign_recalculate = True
                line.foreign_debit = line.debit / self.config_id.foreign_rate
        #TODO: use inverse rate when the currency of the session is the foreign currency
        for payment in split_invoice_receivable_lines.keys():
            line = split_invoice_receivable_lines[payment]
        
            if line.credit > 0:
                line.not_foreign_recalculate = True
                line.foreign_credit = line.credit / self.config_id.foreign_rate
            if line.debit > 0:
                line.not_foreign_recalculate = True
                line.foreign_debit = line.debit / self.config_id.foreign_rate
        return res

    def _create_bank_payment_moves(self, data):
        """
        This method is used to create the bank payment moves, is override to set the foreign amounts in the move lines of the payments."""
        res = super()._create_bank_payment_moves(data)
        payment_to_receivable_lines = res.get("payment_to_receivable_lines")
        payment_method_to_receivable_lines = res.get("payment_method_to_receivable_lines")
        combine_receivables_bank = data.get("combine_receivables_bank")

        for payment_method, amounts in combine_receivables_bank.items():
            lines = payment_method_to_receivable_lines[payment_method]
            for line in lines:
                if line.credit > 0:
                    line.not_foreign_recalculate = True
                    line.foreign_credit = line.credit / self.config_id.foreign_rate
                    _logger.warning(f"LINE CREDIT: {line.credit} - FOREIGN CREDIT: {line.foreign_credit}")
                if line.debit > 0:
                    line.not_foreign_recalculate = True
                    line.foreign_debit = line.debit / self.config_id.foreign_rate
                    _logger.warning(f"LINE DEBIT: {line.debit} - FOREIGN DEBIT: {line.foreign_debit}")

        for payment in payment_to_receivable_lines.keys():
            lines = payment_to_receivable_lines[payment]
            for line in lines:
                if line.credit > 0:
                    line.not_foreign_recalculate = True
                    line.foreign_credit = line.credit / self.config_id.foreign_rate
                    _logger.warning(f"LINE CREDIT: {line.credit} - FOREIGN CREDIT: {line.foreign_credit}")
                if line.debit > 0:
                    line.not_foreign_recalculate = True
                    line.foreign_debit = line.debit / self.config_id.foreign_rate
                    _logger.warning(f"LINE DEBIT: {line.debit} - FOREIGN DEBIT: {line.foreign_debit}")
        return res

    def _create_cash_statement_lines_and_cash_move_lines(self, data):
        """"""
        res = super()._create_cash_statement_lines_and_cash_move_lines(data)
        split_receivables_cash = data.get("split_receivables_cash") or {}
        combine_receivables_cash = data.get("combine_receivables_cash") or {}
        split_cash_statement_lines = res.get("split_cash_statement_lines")
        combine_cash_statement_lines = res.get("combine_cash_statement_lines")
        split_cash_receivable_lines = res.get("split_cash_receivable_lines")
        combine_cash_receivable_lines = res.get("combine_cash_receivable_lines")
        _logger.warning("RES CASH STATEMENT LINES %s", res)
        def _get_lines(container, key):
            if isinstance(container, dict):
                return list(container.get(key, []))
            return list(container or [])

        for payment, amounts in split_receivables_cash.items():
            lines = _get_lines(split_cash_receivable_lines, payment) + _get_lines(
                split_cash_statement_lines,
                payment,
            )

            for line in lines:
                self.set_foreign_amount_in_line(
                    line,
                    amounts.get("foreign_amount", 0.0),
                    amounts.get("amount", 0.0),
                )

        for payment_method, amounts in combine_receivables_cash.items():
            
            lines = _get_lines(combine_cash_receivable_lines, payment_method) + _get_lines(
                combine_cash_statement_lines,
                payment_method,
            )

            for line in lines:
                self.set_foreign_amount_in_line(
                    line,
                    amounts.get("foreign_amount", 0.0),
                    amounts.get("amount", 0.0),
                )

        return res

    def set_foreign_amount_in_line(self, line, foreign_amount, amount=0.0):
        foreign_amount = abs(foreign_amount or 0.0)
        if not foreign_amount:
            return

        other_lines = line.move_id.line_ids.filtered(lambda x: x != line)

        # Aseguramos que el asiento tenga las tasas correctas para evitar inflado de montos
        line.move_id.write(
            {
                "foreign_rate": self.config_id.foreign_rate,
                "foreign_inverse_rate": self.config_id.foreign_inverse_rate,
                "manually_set_rate": True,
            }
        )

        line.not_foreign_recalculate = True
        if abs(line.credit) > 0:
            line.foreign_credit = foreign_amount
            counterpart_candidates = other_lines.filtered(lambda l: abs(l.debit) > 0)
            if counterpart_candidates:
                counterpart = max(counterpart_candidates, key=lambda l: abs(l.debit))
                counterpart.not_foreign_recalculate = True
                counterpart.foreign_debit = foreign_amount

        if abs(line.debit) > 0:
            line.foreign_debit = foreign_amount
            counterpart_candidates = other_lines.filtered(lambda l: abs(l.credit) > 0)
            if counterpart_candidates:
                counterpart = max(counterpart_candidates, key=lambda l: abs(l.credit))
                counterpart.not_foreign_recalculate = True
                counterpart.foreign_credit = foreign_amount
