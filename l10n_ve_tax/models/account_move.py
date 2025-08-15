from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):  
    _inherit = "account.move"


    #TODO:Funciones duplicadas de la logica de negocio de Odoo para el manejo de moneda foranea.
    #FUNCIONES FORANEAS
    def _get_rounded_foreign_base_and_tax_lines(self, round_from_tax_lines=True):
        """ Small helper to extract the base and tax lines for the taxes computation from the current move.
        This is a duplicate of Odoo's logic for handling foreign currency.

        The move could be stored or not and could have some features generating extra journal items acting as
        base lines for the taxes computation (e.g. epd, rounding lines).

        :param round_from_tax_lines:    Indicate if the manual tax amounts of tax journal items should be kept or not.
                                        It only works when the move is stored.
        :return:                        A tuple <base_lines, tax_lines> for the taxes computation.
        """
        self.ensure_one()
        AccountTax = self.env['account.tax']
        is_invoice = self.is_invoice(include_receipts=True)

        if self.id or not is_invoice:
            base_amls = self.line_ids.filtered(lambda line: line.display_type == 'product')
        else:
            base_amls = self.invoice_line_ids.filtered(lambda line: line.display_type == 'product')
        #Lineas tipo producto
        base_lines = [self._prepare_product_foreign_base_line_for_taxes_computation(line) for line in base_amls]
        tax_lines = []
        if self.id:
            # The move is stored so we can add the early payment discount lines directly to reduce the
            # tax amount without touching the untaxed amount.
            epd_amls = self.line_ids.filtered(lambda line: line.display_type == 'epd')

            #Lineas tipo descuento
            base_lines += [self._prepare_epd_foreign_base_line_for_taxes_computation(line) for line in epd_amls]
            cash_rounding_amls = self.line_ids \
                .filtered(lambda line: line.display_type == 'rounding' and not line.tax_repartition_line_id)
            #lineas de rendondeo
            base_lines += [self._prepare_cash_rounding_foreign_base_line_for_taxes_computation(line) for line in cash_rounding_amls]
            AccountTax._add_tax_details_in_base_lines(base_lines, self.company_id)
            tax_amls = self.line_ids.filtered('tax_repartition_line_id')
            tax_lines = [self._prepare_tax_line_for_taxes_computation(tax_line) for tax_line in tax_amls]
            AccountTax._round_base_lines_tax_details(base_lines, self.company_id, tax_lines=tax_lines if round_from_tax_lines else [])
        else:
            # The move is not stored yet so the only thing we have is the invoice lines.
            base_lines += self._prepare_epd_base_lines_for_taxes_computation_from_base_lines(base_amls)
            AccountTax._add_tax_details_in_base_lines(base_lines, self.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, self.company_id)
        return base_lines, tax_lines

    def _prepare_product_foreign_base_line_for_taxes_computation(self, product_line):
        """ Convert an account.move.line having display_type='product' into a base line for the taxes computation.
        This is a duplicate of Odoo's logic for handling foreign currency.

        :param product_line: An account.move.line.
        :return: A base line returned by '_prepare_base_line_for_taxes_computation'.
        """
        self.ensure_one()
        is_invoice = self.is_invoice(include_receipts=True)
        sign = self.direction_sign if is_invoice else 1
        if is_invoice:
            rate = self.foreign_rate
        else:
            rate = (abs(product_line.amount_currency) / abs(product_line.balance)) if product_line.balance else 0.0
        
        return self.env['account.tax']._prepare_foreign_base_line_for_taxes_computation(
            product_line,
            price_unit=product_line.foreign_price,
            quantity=product_line.quantity if is_invoice else 1.0,
            discount=product_line.discount if is_invoice else 0.0,
            rate=rate,
            sign=sign,
            special_mode=False if is_invoice else 'total_excluded',
        )

    #TODO:FOREIGN
    def _prepare_epd_foreign_base_line_for_taxes_computation(self, epd_line):
        """ Convert an account.move.line having display_type='epd' into a base line for the taxes computation.
        This is a duplicate of Odoo's logic for handling foreign currency.

        :param epd_line: An account.move.line.
        :return: A base line returned by '_prepare_base_line_for_taxes_computation'.
        """
        self.ensure_one()
        sign = self.direction_sign
        rate = self.foreign_rate

        return self.env['account.tax']._prepare_foreign_base_line_for_taxes_computation(
            epd_line,
            price_unit=epd_line.foreign_price,
            quantity=1.0,
            sign=sign,
            special_mode='total_excluded',
            special_type='early_payment',

            is_refund=self.move_type in ('out_refund', 'in_refund'),
            rate=rate,
        )
    #foreign function
    def _prepare_cash_rounding_foreign_base_line_for_taxes_computation(self, cash_rounding_line):
        """ Convert an account.move.line having display_type='rounding' into a base line for the taxes computation.
        This is a duplicate of Odoo's logic for handling foreign currency.

        :param cash_rounding_line: An account.move.line.
        :return: A base line returned by '_prepare_base_line_for_taxes_computation'.
        """
        self.ensure_one()
        sign = self.direction_sign
        rate = self.foreign_rate

        return self.env['account.tax']._prepare_foreign_base_line_for_taxes_computation(
            cash_rounding_line,
            price_unit=cash_rounding_line.foreign_price,
            quantity=1.0,
            sign=sign,
            special_mode='total_excluded',
            special_type='cash_rounding',

            is_refund=self.move_type in ('out_refund', 'in_refund'),
            rate=rate,
        )
    #FIN DE FUNCIONES FORANEAS
