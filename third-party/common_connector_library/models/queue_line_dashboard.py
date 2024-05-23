# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models


class QueueLineDashboard(models.AbstractModel):
    _name = "queue.line.dashboard"
    _description = "Queue Line Dashboard"

    def retrieve_dashboard(self, *args, **kwargs):
        return {}

    def get_data(self, **kwargs):
        """
        This method is use to prepare data for the queue line dashboard.
        @param table: Table name of queue line like order_data_queue_line_ept
        @return dashboard_data: It will return the list of data like
        [{'state': {'duration': [len of record, [queue_line_ids]]}},]
        """
        table = kwargs.get('table', '').replace('.', '_')
        data = dict()
        for duration in ['all', 'today', 'yesterday']:
            count, all_ids = 0, list()
            for state in ['draft', 'done', 'failed', 'cancel']:
                key = f"{duration}_{state}"
                line_ids = self._prepare_query(duration, state, table)
                count += len(line_ids)
                all_ids += line_ids
                data.update({key: [len(line_ids), line_ids]})
            data.update({duration: [count, all_ids]})
        data.update({'model': kwargs.get('table')})
        return data

    def _prepare_query(self, duration, state, table):
        qry = f"""
        SELECT 
            id 
            FROM {table} 
            WHERE 
                state = '{state}'
        """
        if duration == 'today':
            qry += " AND create_date >= CURRENT_DATE"
        elif duration == 'yesterday':
            qry += " AND create_date BETWEEN CURRENT_DATE - INTERVAL '1' DAY AND CURRENT_DATE"
        self._cr.execute(qry)
        line_ids = self._cr.dictfetchall()
        return [line_id.get('id') for line_id in line_ids]
