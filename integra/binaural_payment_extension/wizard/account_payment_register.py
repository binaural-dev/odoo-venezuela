from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    is_retention = fields.Boolean(
        string="Is retention",
        default=False,
    )

    payment_type_retention = fields.Selection(
        [
            ("iva", "IVA"),
            ("islr", "ISLR"),
        ],
        default="iva",
        string="Retention type",
    )

    invoice_line_ids = fields.Many2many(
        "account.move.line",
        string="Invoice Lines",
        store=True,
    )

    retention_line_ids = fields.Many2many(
        "account.retention.line",
        string="Retention Lines",
        store=True,
    )

    retention_ref = fields.Char(
        string="Retention reference",
        store=True,
    )
    retention_type = fields.Selection(
        [
            ("out_invoice", "Out invoice"),
            ("in_invoice", "In invoice"),
            ("out_refund", "Out refund"),
            ("in_refund", "In refund"),
            ("out_debit", "Out debit"),
            ("in_debit", "In debit"),
            ("out_contingence", "Out contingence"),
            ("in_contingence", "In contingence"),
        ],
        "Tipo de retención",
        help="Tipo del Comprobante",
        required=True,
        readonly=True,
    )

    def _create_retention(self, payment):
        """
        This method create the retention record and the retention lines records.

        :return: account.retention record

        """
        if self.is_retention and self.payment_type_retention == "iva":
            retention = self.env["account.retention"].create(
                {
                    "name": "Retention IVA",
                    "type_retention": self.payment_type_retention,
                    "partner_id": self.partner_id.id,
                    "company_id": self.company_id.id,
                    "code": self.retention_ref,
                    "type": self.retention_type,
                    # "payment_ids": [(6, 0, payment.id)],
                    "retention_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Retention IVA",
                                "payment_date": self.payment_date,
                                "payment_id": payment.id,
                                "payment_journal_id": self.journal_id.id,
                            },
                        )
                    ],
                }
            )
        if self.is_retention and self.payment_type_retention == "islr":
            retention = self.env["account.retention"].create(
                {
                    "name": "Retention ISLR",
                    "type_retention": self.payment_type_retention,
                    "partner_id": self.partner_id.id,
                    "company_id": self.company_id.id,
                    "code": self.retention_ref,
                    "type": self.retention_type,
                    # "payment_ids": [(6, 0, payment.id)],
                    "retention_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Retention IVA",
                                "payment_date": self.payment_date,
                                "payment_id": payment.id,
                                "payment_journal_id": self.journal_id.id,
                            },
                        )
                    ],
                }
            )
                            
            return retention

    def _create_payments(self):
        
        res = super()._create_payments()
        self._create_retention(res)
        res.write({"is_retention": self.is_retention})
        res.write({"payment_type_retention": self.payment_type_retention})
        res.write({"retention_ref": self.retention_ref})
        res.write({"invoice_line_ids": self.invoice_line_ids})
        return res
