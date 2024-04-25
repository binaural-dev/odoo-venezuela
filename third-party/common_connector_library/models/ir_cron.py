# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from datetime import datetime
from odoo import models


class IrCron(models.Model):
    _inherit = "ir.cron"

    def try_cron_lock(self):
        """ To check scheduler status is running or when nextcall from cron id. It will be used while we are
            performing an operation, and we have a scheduler for that.
            @return: Message like scheduler is running in backend.
        """
        try:
            self._cr.execute("""SELECT id FROM "%s" WHERE id IN %%s FOR UPDATE NOWAIT""" % self._table,
                             [tuple(self.ids)], log_exceptions=False)
            difference = self.nextcall - datetime.now()
            diff_days = difference.days
            if not diff_days < 0:
                days = diff_days * 1440 if diff_days > 0 else 0
                minutes = int(difference.seconds / 60) + days
                return {"result": minutes}
        except:
            return {
                "reason": "This cron task is currently being executed, If you execute this action it may cause "
                          "duplicate records."
            }
