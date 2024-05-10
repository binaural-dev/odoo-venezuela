# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
import itertools
from odoo import models


class DataQueueMixinEpt(models.AbstractModel):
    _name = 'data.queue.mixin.ept'
    _description = 'Data Queue Mixin'

    def delete_data_queue_ept(self, queue_detail=[], is_delete_queue=False):
        """  Uses to delete unused data of queues and log book. logbook deletes which created before 7 days ago.
            @param queue_detail: list of queue records, like product, order queue [['product_queue',
            'order_queue']]
            @param is_delete_queue: Identification to delete queue
        """
        if queue_detail:
            try:
                queue_detail += ['common_log_book_ept']
                queue_detail = list(set(queue_detail))
                for tbl_name in queue_detail:
                    self.delete_data_queue_schedule_activity_ept(tbl_name, is_delete_queue)
                    if is_delete_queue:
                        self._cr.execute("""delete from %s """ % str(tbl_name))
                        continue
                    self._cr.execute(
                        """delete from %s where cast(create_date as Date) <= current_date - %d""" % (str(tbl_name), 7))
            except Exception as error:
                return error
        return True

    def delete_data_queue_schedule_activity_ept(self, tbl_name, is_delete_queue=False):
        """
        Define this method for delete schedule activity for the deleted data queues or
        log book records.
        :param tbl_name: deleted table name
        :param is_delete_queue: True or False
        :return: Boolean (TRUE/FALSE)
        """
        log_book_obj = self.env['common.log.book.ept']
        model_name = tbl_name.replace('_', '.')
        model = log_book_obj._get_model_id(model_name)
        if is_delete_queue:
            self._cr.execute(f"delete from mail_activity where res_model_id={model.id}")
        else:
            self._cr.execute(
                """select id from %s where cast(create_date as Date) <= current_date - %d""" % (str(tbl_name), 7))
            results = self._cr.fetchall()
            records = tuple(set(list(itertools.chain(*results))))
            if records:
                if len(records) == 1:
                    delete_activity = f"delete from mail_activity where res_id={records[0]} and res_model_id={model.id}"
                else:
                    delete_activity = f"delete from mail_activity where res_id in {records} and res_model_id={model.id}"
                self._cr.execute(delete_activity)
        return True
