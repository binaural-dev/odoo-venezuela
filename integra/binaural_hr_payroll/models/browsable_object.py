from odoo.addons.hr_payroll.models.browsable_object import Payslips


@property
def foreign_paid_amount(self):
    return self.dict._get_foreign_paid_amount()


Payslips.foreign_paid_amount = foreign_paid_amount
