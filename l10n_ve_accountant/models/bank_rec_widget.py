from odoo import models, api, Command
from odoo.tools import float_round, float_is_zero

class BankRecWidget(models.Model):
    _inherit = 'bank.rec.widget'
    
    def _action_validate(self):
        """
        Extends the validation process to handle rounding discrepancies 
        between the bank statement line and the selected payments/invoices.
        It ensures the move is perfectly balanced before calling the 
        standard Odoo validation logic.
            The main idea is:
            1. Round all lines to the currency precision immediately.
            2. Calculate the total balance after rounding.
            3. If there's a discrepancy, adjust the bank (liquidity) line to absorb it.
            4. Then call the original validation method, which will now work with perfectly rounded values.
            This way, we avoid any issues with Odoo's internal checks that expect a balanced move.
        """
        self.ensure_one()
        # Use the currency of the company to define rounding precision
        #STEP 0: Get the company currency for rounding purposes
        company_currency = self.st_line_id.company_id.currency_id

        # STEP 1: "Clean" all lines. Convert 377.495 into 377.50 immediately.
        # This matches your loop in the long code where you rounded every 'v'.
        for line in self.line_ids:
            line.balance = float_round(line.balance, precision_rounding=company_currency.rounding)
            if line.currency_id == company_currency:
                line.amount_currency = line.balance

        # STEP 2: Calculate the real discrepancy after rounding
        total_balance = sum(line.balance for line in self.line_ids if line.flag != 'exchange_diff')

        # STEP 3: Force the bank (liquidity) line to absorb the difference
        if not float_is_zero(total_balance, precision_rounding=company_currency.rounding):
            liquidity_line = self.line_ids.filtered(lambda l: l.flag == 'liquidity')
            if liquidity_line:
                # If bank was 1000.0 but payments sum 1000.01, this sets bank to 1000.01
                liquidity_line.balance = float_round(
                    liquidity_line.balance - total_balance, 
                    precision_rounding=company_currency.rounding
                )
                if liquidity_line.currency_id == company_currency:
                    liquidity_line.amount_currency = liquidity_line.balance

        # STEP 4: Call the original Odoo function. 
        return super(BankRecWidget, self)._action_validate()

    
    