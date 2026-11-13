from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PosOrderMfVerificationWizard(models.TransientModel):
    """Resuelve a mano un pedido cuya impresión fiscal quedó "por verificar".

    El PdV los resuelve solo con la máquina antes de imprimir el siguiente
    documento. Llegan aquí los que no pudo resolver, por ejemplo porque se
    emitió otro documento en el medio. Quien resuelve revisa en la máquina
    fiscal si se emitió el documento esperado. Tarea 85447.
    """

    _name = "pos.order.mf.verification.wizard"
    _description = "Resolve a fiscal print to verify"

    order_id = fields.Many2one("pos.order", required=True, readonly=True)
    expected_number = fields.Char(string="Expected fiscal number", compute="_compute_expected")
    expected_serial = fields.Char(string="Expected fiscal printer serial", compute="_compute_expected")
    expected_reportz = fields.Char(string="Expected Z report", compute="_compute_expected")
    result = fields.Selection(
        [
            ("printed", "The fiscal printer printed the document"),
            ("not_printed", "The fiscal printer did not print the document"),
        ],
        required=True,
    )
    mf_invoice_number = fields.Char(string="Fiscal number")
    fiscal_machine = fields.Char(string="Fiscal printer serial")
    mf_reportz = fields.Char(string="Z report")

    @api.depends("order_id")
    def _compute_expected(self):
        for wizard in self:
            before = (wizard.order_id.mf_print_verification or {}).get("before") or {}
            number = before.get("number")
            closures = before.get("dailyClosureCounter")
            wizard.expected_number = str(number + 1) if isinstance(number, int) else False
            wizard.expected_serial = before.get("serial") or False
            # Mismo cálculo que el driver: el Z en curso es el contador + 1.
            wizard.expected_reportz = str(closures + 1) if isinstance(closures, int) else False

    @api.onchange("result")
    def _onchange_result(self):
        if self.result == "printed":
            self.mf_invoice_number = self.mf_invoice_number or self.expected_number
            self.fiscal_machine = self.fiscal_machine or self.expected_serial
            self.mf_reportz = self.mf_reportz or self.expected_reportz

    def action_confirm(self):
        self.ensure_one()
        order = self.order_id
        if not order.mf_print_verification:
            raise UserError(_("The order %s is not waiting for a fiscal print verification.", order.name))
        if self.result == "printed":
            if not self.mf_invoice_number or not self.fiscal_machine:
                raise UserError(_("Enter the fiscal number and the fiscal printer serial."))
            order.write_mf_invoice_data(self.mf_invoice_number, self.fiscal_machine, self.mf_reportz or False)
        order.mf_print_verification = False
        return {"type": "ir.actions.act_window_close"}
