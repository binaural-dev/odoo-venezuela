# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date

class AccountMove(models.Model):
    _inherit = "account.move"

    name = fields.Char(compute="_compute_name_by_sequence")

    @api.depends("state", "journal_id", "date")
    def _compute_name_by_sequence(self):
        for move in self:
            name = move.name or "/"
            if (
                    move.state == "posted"
                    and (not move.name or move.name == "/")
                    and move.journal_id
                    and move.journal_id.sequence_id
            ):
                if (
                        move.move_type in ("out_refund", "in_refund")
                        and move.journal_id.type in ("sale", "purchase")
                        and move.journal_id.refund_sequence
                        and move.journal_id.refund_sequence_id
                ):
                    seq = move.journal_id.refund_sequence_id
                else:
                    seq = move.journal_id.sequence_id
                if move.date:
                    if isinstance(move.date, date) and not isinstance(move.date, datetime):
                        sequence_date = datetime.combine(move.date, datetime.min.time())
                    else:
                        sequence_date = fields.Datetime.to_datetime(move.date)
                    name = seq.next_by_id(sequence_date=sequence_date)
                else:
                    name = seq.next_by_id()
            move.name = name
            move._compute_payment_reference()

    def _constrains_date_sequence(self):
        return True

