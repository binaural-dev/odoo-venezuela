# -*- coding: utf-8 -*-
import pytz

from odoo import fields, models, tools, _
from datetime import datetime
from werkzeug.urls import url_join
from odoo.exceptions import AccessError
from dateutil.relativedelta import relativedelta
from odoo.tools.date_utils import start_of, end_of


class Digest(models.Model):
    _inherit = 'digest.digest'

    is_connector_digest = fields.Boolean()
    module_name = fields.Selection([('woocommerce_ept', 'Woocommerce Connector'),
                                    ('shopify_ept', 'Shopify Connector'),
                                    ('magento_ept', 'Magento Connector'),
                                    ('bol_ept', 'Bol Connector'),
                                    ('ebay_ept', 'Ebay Connector'),
                                    ('amazon_ept', 'Amazon Connector'),
                                    ('amz_vendor_central', 'Amazon Vendor Central')])

    # Connector KPI(s)
    kpi_orders = fields.Boolean("Number Of Orders")
    kpi_shipped_orders = fields.Boolean("Number Of Shipped Orders")
    kpi_cancel_orders = fields.Boolean("Cancel Orders")
    kpi_pending_shipment_on_date = fields.Boolean("Shipment Update Pending As On Date")
    kpi_refund_orders = fields.Boolean("Refund Orders")
    kpi_avg_order_value = fields.Boolean("Average Order Value")
    kpi_late_deliveries = fields.Boolean("Late Delivery Orders")
    kpi_on_shipping_orders = fields.Boolean("On Time Shipping Ratio")

    # Connector KPI(s) Value
    kpi_orders_value = fields.Integer()
    kpi_shipped_orders_value = fields.Integer()
    kpi_cancel_orders_value = fields.Integer()
    kpi_pending_shipment_on_date_value = fields.Integer()
    kpi_refund_orders_value = fields.Integer()
    kpi_avg_order_value_value = fields.Monetary()
    kpi_late_deliveries_value = fields.Integer()
    kpi_late_deliveries_value_bt_four_seven = fields.Integer()
    kpi_late_deliveries_value_seven_up = fields.Integer()
    kpi_on_shipping_orders_value = fields.Integer()

    def _prepare_domain_based_on_connector(self):
        """
        This method is need to override in all connector for prepare domain based on instance.
        """
        return True

    def _prepare_query_domain(self, domain, table_ref):
        """
        This method is used to prepared dynamic domain based on query string and query table reference.
        @return: domain of query string
        """
        where_string = ""
        for d in domain:
            if d[2]:
                where_string += f"AND {table_ref + d[0]} {d[1]} {d[2]}  "
        return where_string

    def get_account_total_revenue(self, domain):
        """
        Use: To get the list of connector's account total revenue.
        @return: total number of connector's sale orders ids and action for sale orders of current instance.
        """
        for record in self:
            start, end, company = record._get_kpi_compute_parameters()
            domain = self._prepare_query_domain(domain, 'move.')
            query = f"""SELECT -SUM(line.balance)
                FROM account_move_line line
                JOIN account_move move ON move.id = line.move_id
                JOIN account_account account ON account.id = line.account_id
                WHERE line.company_id = {company.id} AND line.date >= '{start}' AND line.date <= '{end}'
                AND account.internal_group = 'income'
                AND move.state = 'posted' {domain}"""
            self._cr.execute(query)
            query_res = self._cr.fetchone()
            record.kpi_account_total_revenue_value = query_res and query_res[0] or 0

    def get_total_orders_count(self, domain):
        """
        Use: To get the list of connector's total orders count.
        @return: total number of connector's sale orders ids and action for sale orders of current instance.
        """
        for record in self:
            start, end, company = record._get_kpi_compute_parameters()
            domain = self._prepare_query_domain(domain, 'so.')
            query = f"""select count(*) from sale_order so where so.company_id ={company.id} 
                AND so.date_order >= '{start}' AND so.date_order <= '{end}' 
                and state in ('sale','done') {domain}"""
            self._cr.execute(query)
            query_res = self._cr.fetchone()
            record.kpi_orders_value = query_res and query_res[0] or 0

    def get_shipped_orders_count(self, domain):
        """
        Use: To get the list of connector's Total shipped orders count.
        @return: total number of connector's sale orders ids and action for sale orders of current instance.
        """
        for record in self:
            start, end, company = record._get_kpi_compute_parameters()
            domain = self._prepare_query_domain(domain, 'sp.')
            query = f"""select count(*) from stock_picking sp
                 inner join sale_order so on so.procurement_group_id=sp.group_id inner 
                 join stock_location on stock_location.id=sp.location_dest_id and stock_location.usage='customer' 
                 where sp.state != 'cancel' and sp.company_id={company.id} 
                 and sp.date_done >= '{start}' and sp.date_done <= '{end}' {domain}"""
            self._cr.execute(query)
            query_res = self._cr.fetchone()
            record.kpi_shipped_orders_value = query_res and query_res[0] or 0

    def get_pending_shipment_on_date_count(self, domain):
        """
        Use: To get the list of connector's pending shipment on date count.
        @return: total number of connector's sale orders ids and action for sale orders of current instance.
        """
        for record in self:
            start, end, company = record._get_kpi_compute_parameters()
            domain = self._prepare_query_domain(domain, 'sp.')
            query = f"""select count(*) from stock_picking sp
                 inner join sale_order so on so.procurement_group_id=sp.group_id inner 
                 join stock_location on stock_location.id=sp.location_dest_id and stock_location.usage='customer' 
                 where sp.state != 'cancel' and sp.company_id={company.id} 
                 and sp.scheduled_date >= '{start}' and sp.scheduled_date <= '{end}' {domain}"""
            self._cr.execute(query)
            query_res = self._cr.fetchone()
            record.kpi_pending_shipment_on_date_value = query_res and query_res[0] or 0

    def get_cancel_orders_count(self, domain):
        """
        Use: To get the list of connector's Total cancel orders count.
        @return: total number of connector's sale orders ids and action for sale orders of current instance.
        """
        for record in self:
            start, end, company = record._get_kpi_compute_parameters()
            domain = self._prepare_query_domain(domain, 'so.')
            query = f"""select count(*) from sale_order so where so.company_id ={company.id}
                AND so.date_order >= '{start}' AND so.date_order <= '{end}' and state='cancel' {domain}"""
            self._cr.execute(query)
            query_res = self._cr.fetchone()
            record.kpi_cancel_orders_value = query_res and query_res[0] or 0

    def get_orders_average(self, domain):
        """
        Use: To get the list of connector's Total average of orders.
        @return: total number of connector's sale orders ids and action for sale orders of current instance.
        """
        for record in self:
            start, end, company = record._get_kpi_compute_parameters()
            domain = self._prepare_query_domain(domain, 'so.')
            query = f"""select sum(amount_untaxed) from sale_order so
                        where so.company_id ={company.id} AND so.date_order >= '{start}' AND so.date_order <= '{end}' 
                        and state in ('sale','done') {domain}"""
            self._cr.execute(query)
            query_res = self._cr.fetchone()
            total_sales = 0.0
            if query_res and query_res[0]:
                total_sales += query_res[0]
            total_orders = record.kpi_orders_value if record.kpi_orders_value else 1
            record.kpi_avg_order_value_value = total_sales / total_orders

    def get_refund_orders_count(self, domain):
        """
        Use: To get the list of connector's Total refund orders count.
        @return: total number of connector's sale orders ids and action for sale orders of current instance.
        """
        for record in self:
            start, end, company = record._get_kpi_compute_parameters()
            domain = self._prepare_query_domain(domain, 'am.')
            query = f"""select count(*) from account_move am
                where am.company_id = {company.id} AND am.invoice_date > '{start}' 
                AND am.invoice_date <= '{end}' and am.move_type='out_refund' {domain} group by am.id"""
            self._cr.execute(query)
            query_res = self._cr.fetchone()
            total_refund_orders = []
            if query_res != None:
                total_refund_orders.append(query_res and query_res[0])
            record.kpi_refund_orders_value = len(total_refund_orders) or 0

    def get_late_delivery_orders_count(self, domain):
        """
        Use: To get the list of connector's Total late delivery orders count.
        @return: total number of connector's sale orders ids and action for sale orders of current instance.
        """
        for record in self:
            domain = self._prepare_query_domain(domain, '')
            query = f"""select * from(
                select count(*) as first from stock_picking where state='done' {domain} and (date(date_done)-date(scheduled_date)) between 1 and 3 
                union all
                select count(*) as second from stock_picking where state='done' {domain} and (date(date_done)-date(scheduled_date)) between 4 and 7 
                union all
                select count(*) as third from stock_picking where state='done' {domain} and (date(date_done)-date(scheduled_date)) > 7
                )T"""
            self._cr.execute(query)
            query_res = self._cr.fetchall()
            late_deliveries_bt_one_three = 0
            late_deliveries_bt_four_seven = 0
            late_deliveries_seven_up = 0
            if query_res and query_res[0][0]:
                late_deliveries_bt_one_three = query_res and query_res[0][0] or 0
            if query_res and query_res[1][0]:
                late_deliveries_bt_four_seven = query_res and query_res[1][0] or 0
            if query_res and query_res[2][0]:
                late_deliveries_seven_up = query_res and query_res[2][0] or 0
            record.kpi_late_deliveries_value = late_deliveries_bt_one_three
            record.kpi_late_deliveries_value_bt_four_seven = late_deliveries_bt_four_seven
            record.kpi_late_deliveries_value_seven_up = late_deliveries_seven_up

    def get_on_time_shipping_ratio(self, domain):
        """
        Use: To get the list of connector's On Time shipping ratio.
        @return: total number of connector's sale orders ids and action for sale orders of current instance.
        """
        for record in self:
            domain = self._prepare_query_domain(domain, '')
            end_date = datetime.today()
            if self._context.get('end_datetime'):
                end_date = self._context.get('end_datetime')
            on_date = end_date + relativedelta(days=-1)
            query = f"""select * from (                                                                                        
                select count(*) as first from stock_picking as sp where sp.state='done' and date(sp.date_done) = date(sp.scheduled_date) and date(sp.scheduled_date) = '{on_date}' {domain}
                union all
                select count(*) as second from stock_picking as sp2 where sp2.state='done' and  date(sp2.scheduled_date) = '{on_date}' {domain}
                )T"""
            self._cr.execute(query)
            query_res = self._cr.fetchall()
            shipping_count = 0
            if query_res and query_res[0][0] and query_res[1][0] != 0:
                shipping_count = query_res and query_res[0][0] / query_res[1][0] * 100
            record.kpi_on_shipping_orders_value = shipping_count

    def _action_send_to_user(self, user, tips_count=1, consume_tips=True):
        """
        This Method is used to set email template of connector.
        """
        if self.is_connector_digest:
            unsubscribe_token = self._get_unsubscribe_token(user.id)

            rendered_body = self.env['mail.render.mixin']._render_template(
                'common_connector_library.connector_digest_mail_main',
                'digest.digest',
                self.ids,
                engine='qweb_view',
                add_context={
                    'title': self.name,
                    'top_button_label': _('Connect'),
                    'top_button_url': self.get_base_url(),
                    'company': user.company_id,
                    'user': user,
                    'unsubscribe_token': unsubscribe_token,
                    'tips_count': tips_count,
                    'formatted_date': datetime.today().strftime('%B %d, %Y'),
                    'display_mobile_banner': True,
                    'kpi_data': self._compute_kpis(user.company_id, user),
                    'tips': self._compute_tips(user.company_id, user, tips_count=tips_count, consumed=consume_tips),
                    'preferences': self._compute_preferences(user.company_id, user),
                },
                post_process=True,
                options={'preserve_comments': True}
            )[self.id]
            full_mail = self.env['mail.render.mixin']._render_encapsulate(
                'common_connector_library.connector_digest_mail_layout',
                rendered_body,
                add_context={
                    'company': user.company_id,
                    'user': user,
                },
            )
            # create a mail_mail based on values, without attachments
            unsub_url = url_join(self.get_base_url(),
                                 f'/digest/{self.id}/unsubscribe?token={unsubscribe_token}&user_id={user.id}&one_click=1')
            mail_values = {
                'auto_delete': True,
                'author_id': self.env.user.partner_id.id,
                'body_html': full_mail,
                'email_from': (
                        self.company_id.partner_id.email_formatted
                        or self.env.user.email_formatted
                        or self.env.ref('base.user_root').email_formatted
                ),
                'email_to': user.email_formatted,
                # Add headers that allow the MUA to offer a one click button to unsubscribe (requires DKIM to work)
                'headers': {
                    'List-Unsubscribe': f'<{unsub_url}>',
                    'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
                    'X-Auto-Response-Suppress': 'OOF',  # avoid out-of-office replies from MS Exchange
                },
                'state': 'outgoing',
                'subject': '%s: %s' % (user.company_id.name, self.name),
            }
            self.env['mail.mail'].sudo().create(mail_values)
            return True
        return super(Digest, self)._action_send_to_user(user)

    def _compute_kpis(self, company, user):
        """ This Method is used to compute kpi data based on Yesterday, Last week, Last month, Last quarter. """
        if self.is_connector_digest:
            self.ensure_one()
            digest_fields = self._get_kpi_fields()
            invalid_fields = []
            kpis = [
                dict(kpi_name=field_name,
                     kpi_fullname=self.env['ir.model.fields']._get(self._name, field_name).field_description,
                     kpi_action=False,
                     kpi_col1=dict(),
                     kpi_col2=dict(),
                     kpi_col3=dict(),
                     kpi_col4=dict(),
                     )
                for field_name in digest_fields
            ]
            # kpis_actions = self._compute_kpis_actions(company, user)

            for col_index, (tf_name, tf) in enumerate(self._compute_timeframes(company)):
                digest = self.with_context(start_datetime=tf[0][0], end_datetime=tf[0][1]).with_user(user).with_company(
                    company)
                previous_digest = self.with_context(start_datetime=tf[1][0], end_datetime=tf[1][1]).with_user(
                    user).with_company(company)
                for index, field_name in enumerate(digest_fields):
                    kpi_values = kpis[index]
                    self.with_context(start_datetime=tf[0][0],
                                      end_datetime=tf[0][1])._prepare_domain_based_on_connector()
                    # kpi_values['kpi_action'] = kpis_actions.get(field_name)
                    try:
                        compute_value = digest[field_name + '_value']
                        # Context start and end date is different each time so invalidate to recompute.
                        digest.invalidate_model([field_name + '_value'])
                        previous_value = previous_digest[field_name + '_value']
                        # Context start and end date is different each time so invalidate to recompute.
                        previous_digest.invalidate_model([field_name + '_value'])
                    except AccessError:  # no access rights -> just skip that digest details from that user's digest email
                        invalid_fields.append(field_name)
                        continue
                    margin = self._get_margin_value(compute_value, previous_value)
                    if self._fields['%s_value' % field_name].type == 'monetary':
                        converted_amount = tools.format_decimalized_amount(compute_value)
                        compute_value = self._format_currency_amount(converted_amount, company.currency_id)
                    kpi_values['kpi_col%s' % (col_index + 1)].update({
                        'value': compute_value,
                        'margin': margin,
                        'col_subtitle': tf_name,
                    })
                    if kpi_values['kpi_name'] == 'kpi_late_deliveries':
                        kpi_values['kpi_col1'].update({'value': self.kpi_late_deliveries_value})
                        kpi_values['kpi_col2'].update({'value': self.kpi_late_deliveries_value_bt_four_seven})
                        kpi_values['kpi_col3'].update({'value': self.kpi_late_deliveries_value_seven_up})

            # filter failed KPIs
            return [kpi for kpi in kpis if kpi['kpi_name'] not in invalid_fields]
        return super(Digest, self)._compute_kpis(company, user)

    def _compute_timeframes(self, company):
        """
        This Method is override to compute timeframe based on Yesterday, Last week, Last month, Last quarter.
        """
        if self.is_connector_digest:
            start_datetime = datetime.utcnow()
            tz_name = company.resource_calendar_id.tz
            quarter_start_datetime = start_of(start_datetime + relativedelta(months=-3), 'quarter')
            quarter_end_datetime = end_of(quarter_start_datetime, 'quarter')
            if tz_name:
                start_datetime = pytz.timezone(tz_name).localize(start_datetime)
                quarter_start_datetime = pytz.timezone(tz_name).localize(quarter_start_datetime)
                quarter_end_datetime = pytz.timezone(tz_name).localize(quarter_end_datetime)
            return [
                (_('Yesterday'), (
                    (start_datetime + relativedelta(days=-1), start_datetime),
                    (start_datetime + relativedelta(days=-2), start_datetime + relativedelta(days=-1)))),
                (_('Last Week'), (
                    (start_datetime + relativedelta(weeks=-1), start_datetime),
                    (start_datetime + relativedelta(weeks=-2), start_datetime + relativedelta(weeks=-1)))),
                (_('Last Month'), (
                    (start_datetime + relativedelta(months=-1), start_datetime),
                    (start_datetime + relativedelta(months=-2), start_datetime + relativedelta(months=-1)))),
                (_('Last Quarter'), ((quarter_start_datetime, quarter_end_datetime),
                                     (quarter_start_datetime + relativedelta(months=-3),
                                      quarter_start_datetime + relativedelta(days=-1))))
            ]
        return super(Digest, self)._compute_timeframes(company)
