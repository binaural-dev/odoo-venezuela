# -*- coding: utf-8 -*-

from collections import defaultdict
import json

from odoo import models
from odoo.fields import Domain


class ProjectProject(models.Model):
    _inherit = 'project.project'

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _get_foreign_currency_symbol(self):
        """Return the symbol of the company foreign currency."""
        currency = self.company_id.foreign_currency_id
        return currency.symbol if currency else ''
    # -------------------------------------------------------------------------
    # Revenues from Sale Order Lines (override sale_project)
    # -------------------------------------------------------------------------
    def _get_revenues_items_from_sol(self, domain=None, with_action=True):
        """Build the revenues items from the project sale order lines.

        Reads the stored foreign split fields of the sale order lines
        (``foreign_amount_invoiced`` / ``foreign_amount_to_invoice``) together
        with the core untaxed amounts, so the foreign amounts keep the same
        "real invoiced / forecast to invoice" criterion of the sale order line.
        """
        sale_line_read_group = self.env['sale.order.line'].sudo()._read_group(
            self._get_profitability_sale_order_items_domain(domain),
            ['currency_id', 'product_id', 'is_downpayment'],
            ['id:array_agg', 'untaxed_amount_to_invoice:sum', 'untaxed_amount_invoiced:sum',
             'foreign_amount_to_invoice:sum', 'foreign_amount_invoiced:sum'],
        )
        display_sol_action = with_action and len(self) == 1 and self.env.user.has_group('sales_team.group_sale_salesman')
        revenues_dict = {}
        total_to_invoice = total_invoiced = 0.0
        total_foreign_to_invoice = total_foreign_invoiced = 0.0
        data = []
        sequence_per_invoice_type = self._get_profitability_sequence_per_invoice_type()
        if sale_line_read_group:
            convert_company = self.company_id or self.env.company

            sols_per_product = defaultdict(lambda: [0.0, 0.0, [], 0.0, 0.0])
            downpayment_amount_invoiced = 0
            downpayment_foreign_invoiced = 0.0
            downpayment_sol_ids = []
            for (
                currency, product, is_downpayment, sol_ids,
                untaxed_amount_to_invoice, untaxed_amount_invoiced,
                foreign_amount_to_invoice, foreign_amount_invoiced,
            ) in sale_line_read_group:
                if is_downpayment:
                    downpayment_amount_invoiced += currency._convert(
                        untaxed_amount_invoiced, convert_company.currency_id, convert_company, round=False
                    )
                    downpayment_sol_ids += sol_ids
                else:
                    sols_per_product[product.id][0] += currency._convert(
                        untaxed_amount_to_invoice, convert_company.currency_id, convert_company
                    )
                    sols_per_product[product.id][1] += currency._convert(
                        untaxed_amount_invoiced, convert_company.currency_id, convert_company
                    )
                    sols_per_product[product.id][2] += sol_ids
                    sols_per_product[product.id][3] += foreign_amount_to_invoice or 0.0
                    sols_per_product[product.id][4] += foreign_amount_invoiced or 0.0

            if downpayment_amount_invoiced:
                if downpayment_sol_ids:
                    downpayment_foreign_invoiced = sum(
                        -line.foreign_balance
                        for line in self.env['account.move.line'].sudo().search([
                            ('sale_line_ids', 'in', downpayment_sol_ids),
                            ('move_id.move_type', 'in', ('out_invoice', 'out_refund')),
                            ('parent_state', '!=', 'cancel'),
                        ])
                    )
                downpayments_data = {
                    'id': 'downpayments',
                    'sequence': sequence_per_invoice_type['downpayments'],
                    'invoiced': downpayment_amount_invoiced,
                    'to_invoice': -downpayment_amount_invoiced,
                    'foreign_invoiced': downpayment_foreign_invoiced,
                    'foreign_to_invoice': -downpayment_foreign_invoiced,
                }
                if with_action and (
                    self.env.user.has_group('sales_team.group_sale_salesman_all_leads')
                    or self.env.user.has_group('account.group_account_invoice')
                    or self.env.user.has_group('account.group_account_readonly')
                ):
                    invoices = self.env['account.move'].search([
                        ('line_ids.sale_line_ids', 'in', downpayment_sol_ids)
                    ])
                    args = ['downpayments', [('id', 'in', invoices.ids)]]
                    if len(invoices) == 1:
                        args.append(invoices.id)
                    downpayments_data['action'] = {
                        'name': 'action_profitability_items',
                        'type': 'object',
                        'args': json.dumps(args),
                    }
                data += [downpayments_data]
                total_invoiced += downpayment_amount_invoiced
                total_to_invoice -= downpayment_amount_invoiced
                total_foreign_invoiced += downpayment_foreign_invoiced
                total_foreign_to_invoice -= downpayment_foreign_invoiced

            product_read_group = self.env['product.product'].sudo()._read_group(
                [('id', 'in', list(sols_per_product))],
                ['invoice_policy', 'service_type', 'type'],
                ['id:array_agg'],
            )
            service_policy_to_invoice_type = self._get_service_policy_to_invoice_type()
            general_to_service_map = self.env['product.template']._get_general_to_service_map()
            for invoice_policy, service_type, type_, product_ids in product_read_group:
                service_policy = None
                if type_ == 'service':
                    service_policy = general_to_service_map.get(
                        (invoice_policy, service_type),
                        'ordered_prepaid')
                for product_id, (
                    amount_to_invoice, amount_invoiced, sol_ids,
                    foreign_amount_to_invoice, foreign_amount_invoiced,
                ) in sols_per_product.items():
                    if product_id in product_ids:
                        invoice_type = service_policy_to_invoice_type.get(service_policy, 'materials')
                        revenue = revenues_dict.setdefault(invoice_type, {
                            'invoiced': 0.0, 'to_invoice': 0.0,
                            'foreign_invoiced': 0.0, 'foreign_to_invoice': 0.0,
                        })
                        revenue['to_invoice'] += amount_to_invoice
                        total_to_invoice += amount_to_invoice
                        revenue['invoiced'] += amount_invoiced
                        total_invoiced += amount_invoiced
                        revenue['foreign_to_invoice'] += foreign_amount_to_invoice
                        total_foreign_to_invoice += foreign_amount_to_invoice
                        revenue['foreign_invoiced'] += foreign_amount_invoiced
                        total_foreign_invoiced += foreign_amount_invoiced
                        if display_sol_action and invoice_type in ['service_revenues', 'materials']:
                            revenue.setdefault('record_ids', []).extend(sol_ids)

            if display_sol_action:
                section_name = 'materials'
                materials = revenues_dict.get(section_name, {})
                sale_order_items = self.env['sale.order.line'] \
                    .browse(materials.pop('record_ids', [])) \
                    ._filtered_access('read')
                if sale_order_items:
                    args = [section_name, [('id', 'in', sale_order_items.ids)]]
                    if len(sale_order_items) == 1:
                        args.append(sale_order_items.id)
                    action_params = {
                        'name': 'action_profitability_items',
                        'type': 'object',
                        'args': json.dumps(args),
                    }
                    if len(sale_order_items) == 1:
                        action_params['res_id'] = sale_order_items.id
                    materials['action'] = action_params

        sequence_per_invoice_type = self._get_profitability_sequence_per_invoice_type()
        data += [{
            'id': invoice_type,
            'sequence': sequence_per_invoice_type[invoice_type],
            **vals,
        } for invoice_type, vals in revenues_dict.items()]
        return {
            'data': data,
            'total': {
                'to_invoice': total_to_invoice,
                'invoiced': total_invoiced,
                'foreign_to_invoice': total_foreign_to_invoice,
                'foreign_invoiced': total_foreign_invoiced,
            },
        }

    # -------------------------------------------------------------------------
    # Costs from Purchase Bills (override project_account)
    # -------------------------------------------------------------------------
    def _get_costs_items_from_purchase(self, domain, profitability_items, with_action=True):
        """Build the "other purchase costs" costs item from vendor bills.

        The foreign amounts are read from the real ``foreign_balance`` of each
        account.move.line, prorated with its own analytic distribution.
        """
        account_move_lines = self.env['account.move.line'].sudo().search_fetch(
            domain + [('analytic_distribution', 'in', self.account_id.ids)],
            ['balance', 'foreign_balance', 'parent_state', 'company_currency_id', 'analytic_distribution', 'move_id', 'date'],
        )
        if account_move_lines:
            amount_invoiced = amount_to_invoice = 0.0
            foreign_amount_invoiced = foreign_amount_to_invoice = 0.0
            for move_line in account_move_lines:
                line_balance = move_line.company_currency_id._convert(
                    from_amount=move_line.balance, to_currency=self.currency_id, date=move_line.date
                )
                line_foreign_balance = move_line.foreign_balance or 0.0
                analytic_contribution = sum(
                    percentage for ids, percentage in move_line.analytic_distribution.items()
                    if str(self.account_id.id) in ids.split(',')
                ) / 100.
                if move_line.parent_state == 'draft':
                    amount_to_invoice -= line_balance * analytic_contribution
                    foreign_amount_to_invoice -= line_foreign_balance * analytic_contribution
                else:
                    amount_invoiced -= line_balance * analytic_contribution
                    foreign_amount_invoiced -= line_foreign_balance * analytic_contribution

            if amount_invoiced != 0 or amount_to_invoice != 0:
                costs = profitability_items['costs']
                section_id = 'other_purchase_costs'
                bills_costs = {
                    'id': section_id,
                    'sequence': self._get_profitability_sequence_per_invoice_type()[section_id],
                    'billed': amount_invoiced,
                    'to_bill': amount_to_invoice,
                    'foreign_billed': foreign_amount_invoiced,
                    'foreign_to_bill': foreign_amount_to_invoice,
                }
                if with_action:
                    bills_costs['action'] = self._get_action_for_profitability_section(
                        account_move_lines.move_id.ids, section_id
                    )
                costs['data'].append(bills_costs)
                costs['total']['billed'] += amount_invoiced
                costs['total']['to_bill'] += amount_to_invoice
                costs['total'].setdefault('foreign_billed', 0.0)
                costs['total'].setdefault('foreign_to_bill', 0.0)
                costs['total']['foreign_billed'] += foreign_amount_invoiced
                costs['total']['foreign_to_bill'] += foreign_amount_to_invoice

    # -------------------------------------------------------------------------
    # Revenues/Costs from Invoices (override sale_project)
    # -------------------------------------------------------------------------
    def _get_items_from_invoices(self, excluded_move_line_ids=None, with_action=True):
        """Build the revenues/costs items from invoices not linked to sale lines.

        The foreign amounts are read from the real ``foreign_balance`` of each
        account.move.line, prorated with its own analytic distribution.
        """
        if excluded_move_line_ids is None:
            excluded_move_line_ids = []
        aml_fetch_fields = [
            'balance', 'foreign_balance', 'parent_state', 'company_currency_id',
            'analytic_distribution', 'move_id', 'display_type', 'date',
        ]
        invoices_move_lines = self.env['account.move.line'].sudo().search_fetch(
            Domain.AND([
                self._get_items_from_invoices_domain([('id', 'not in', excluded_move_line_ids)]),
                [('analytic_distribution', 'in', self.account_id.ids)]
            ]),
            aml_fetch_fields,
        )
        res = {
            'revenues': {
                'data': [], 'total': {
                    'invoiced': 0.0, 'to_invoice': 0.0,
                    'foreign_invoiced': 0.0, 'foreign_to_invoice': 0.0,
                }
            },
            'costs': {
                'data': [], 'total': {
                    'billed': 0.0, 'to_bill': 0.0,
                    'foreign_billed': 0.0, 'foreign_to_bill': 0.0,
                }
            },
        }
        if invoices_move_lines:
            revenues_lines = []
            cogs_lines = []
            for move_line in invoices_move_lines:
                if move_line['display_type'] == 'cogs':
                    cogs_lines.append(move_line)
                else:
                    revenues_lines.append(move_line)
            for move_lines, ml_type in ((revenues_lines, 'revenues'), (cogs_lines, 'costs')):
                amount_invoiced = amount_to_invoice = 0.0
                foreign_amount_invoiced = foreign_amount_to_invoice = 0.0
                for move_line in move_lines:
                    currency = move_line.company_currency_id
                    line_balance = currency._convert(
                        move_line.balance, self.currency_id, self.company_id, move_line.date
                    )
                    line_foreign_balance = move_line.foreign_balance or 0.0
                    analytic_contribution = sum(
                        percentage for ids, percentage in move_line.analytic_distribution.items()
                        if str(self.account_id.id) in ids.split(',')
                    ) / 100.
                    if move_line.parent_state == 'draft':
                        amount_to_invoice -= line_balance * analytic_contribution
                        foreign_amount_to_invoice -= line_foreign_balance * analytic_contribution
                    else:
                        amount_invoiced -= line_balance * analytic_contribution
                        foreign_amount_invoiced -= line_foreign_balance * analytic_contribution
                if amount_invoiced != 0 or amount_to_invoice != 0:
                    section_id = 'other_invoice_revenues' if ml_type == 'revenues' else 'cost_of_goods_sold'
                    invoices_items = {
                        'id': section_id,
                        'sequence': self._get_profitability_sequence_per_invoice_type()[section_id],
                        'invoiced' if ml_type == 'revenues' else 'billed': amount_invoiced,
                        'to_invoice' if ml_type == 'revenues' else 'to_bill': amount_to_invoice,
                        'foreign_invoiced' if ml_type == 'revenues' else 'foreign_billed': foreign_amount_invoiced,
                        'foreign_to_invoice' if ml_type == 'revenues' else 'foreign_to_bill': foreign_amount_to_invoice,
                    }
                    if with_action and (
                        self.env.user.has_group('sales_team.group_sale_salesman_all_leads')
                        or self.env.user.has_group('account.group_account_invoice')
                        or self.env.user.has_group('account.group_account_readonly')
                    ):
                        invoices_items['action'] = self._get_action_for_profitability_section(
                            invoices_move_lines.move_id.ids, section_id
                        )
                    res[ml_type] = {
                        'data': [invoices_items],
                        'total': {
                            'invoiced' if ml_type == 'revenues' else 'billed': amount_invoiced,
                            'to_invoice' if ml_type == 'revenues' else 'to_bill': amount_to_invoice,
                            'foreign_invoiced' if ml_type == 'revenues' else 'foreign_billed': foreign_amount_invoiced,
                            'foreign_to_invoice' if ml_type == 'revenues' else 'foreign_to_bill': foreign_amount_to_invoice,
                        },
                    }
        return res

    # -------------------------------------------------------------------------
    # Add Invoice Items (override sale_project to accumulate foreign totals)
    # -------------------------------------------------------------------------
    def _add_invoice_items(self, domain, profitability_items, with_action=True):
        """Merge the invoice items (excluding sale-line invoices) into the items."""
        sale_lines = self.env['sale.order.line'].sudo()._read_group(
            self._get_profitability_sale_order_items_domain(domain),
            [],
            ['id:recordset'],
        )[0][0]
        items_from_invoices = self._get_items_from_invoices(
            excluded_move_line_ids=sale_lines.invoice_lines.ids,
            with_action=with_action,
        )
        profitability_items['revenues']['data'] += items_from_invoices['revenues']['data']
        profitability_items['revenues']['total']['to_invoice'] += items_from_invoices['revenues']['total']['to_invoice']
        profitability_items['revenues']['total']['invoiced'] += items_from_invoices['revenues']['total']['invoiced']
        profitability_items['revenues']['total'].setdefault('foreign_to_invoice', 0.0)
        profitability_items['revenues']['total'].setdefault('foreign_invoiced', 0.0)
        profitability_items['revenues']['total']['foreign_to_invoice'] += items_from_invoices['revenues']['total']['foreign_to_invoice']
        profitability_items['revenues']['total']['foreign_invoiced'] += items_from_invoices['revenues']['total']['foreign_invoiced']

        profitability_items['costs']['data'] += items_from_invoices['costs']['data']
        profitability_items['costs']['total']['to_bill'] += items_from_invoices['costs']['total']['to_bill']
        profitability_items['costs']['total']['billed'] += items_from_invoices['costs']['total']['billed']
        profitability_items['costs']['total'].setdefault('foreign_to_bill', 0.0)
        profitability_items['costs']['total'].setdefault('foreign_billed', 0.0)
        profitability_items['costs']['total']['foreign_to_bill'] += items_from_invoices['costs']['total']['foreign_to_bill']
        profitability_items['costs']['total']['foreign_billed'] += items_from_invoices['costs']['total']['foreign_billed']

    # -------------------------------------------------------------------------
    # AAL Items (override project_account)
    # -------------------------------------------------------------------------
    def _get_items_from_aal(self, with_action=True):
        """Build the revenues/costs items from analytic lines without a move line.

        The foreign amounts are read from the ``foreign_amount`` of each
        analytic line.
        """
        domain = Domain.AND([
            self._get_domain_aal_with_no_move_line(),
            Domain('category', 'not in', ['manufacturing_order', 'picking_entry']),
        ])
        aal_other_search = self.env['account.analytic.line'].sudo().search_read(
            domain, ['id', 'amount', 'foreign_amount', 'currency_id']
        )
        if not aal_other_search:
            return {
                'revenues': {'data': [], 'total': {'invoiced': 0.0, 'to_invoice': 0.0, 'foreign_invoiced': 0.0, 'foreign_to_invoice': 0.0}},
                'costs': {'data': [], 'total': {'billed': 0.0, 'to_bill': 0.0, 'foreign_billed': 0.0, 'foreign_to_bill': 0.0}},
            }
        dict_amount_per_currency_id = defaultdict(lambda: {'costs': 0.0, 'revenues': 0.0, 'foreign_costs': 0.0, 'foreign_revenues': 0.0})
        set_currency_ids = {self.currency_id.id}
        cost_ids = []
        revenue_ids = []
        for aal in aal_other_search:
            set_currency_ids.add(aal['currency_id'][0])
            aal_amount = aal['amount']
            aal_foreign_amount = aal.get('foreign_amount', 0.0) or 0.0
            if aal_amount < 0.0:
                dict_amount_per_currency_id[aal['currency_id'][0]]['costs'] += aal_amount
                dict_amount_per_currency_id[aal['currency_id'][0]]['foreign_costs'] += aal_foreign_amount
                cost_ids.append(aal['id'])
            else:
                dict_amount_per_currency_id[aal['currency_id'][0]]['revenues'] += aal_amount
                dict_amount_per_currency_id[aal['currency_id'][0]]['foreign_revenues'] += aal_foreign_amount
                revenue_ids.append(aal['id'])

        total_revenues = total_costs = 0.0
        total_foreign_revenues = total_foreign_costs = 0.0
        for currency_id, dict_amounts in dict_amount_per_currency_id.items():
            currency = self.env['res.currency'].browse(currency_id).with_prefetch(dict_amount_per_currency_id)
            total_revenues += currency._convert(dict_amounts['revenues'], self.currency_id, self.company_id)
            total_costs += currency._convert(dict_amounts['costs'], self.currency_id, self.company_id)
            total_foreign_revenues += dict_amounts['foreign_revenues']
            total_foreign_costs += dict_amounts['foreign_costs']

        profitability_sequence_per_invoice_type = self._get_profitability_sequence_per_invoice_type()
        revenues = {
            'id': 'other_revenues_aal',
            'sequence': profitability_sequence_per_invoice_type['other_revenues_aal'],
            'invoiced': total_revenues,
            'to_invoice': 0.0,
            'foreign_invoiced': total_foreign_revenues,
            'foreign_to_invoice': 0.0,
        }
        costs = {
            'id': 'other_costs_aal',
            'sequence': profitability_sequence_per_invoice_type['other_costs_aal'],
            'billed': total_costs,
            'to_bill': 0.0,
            'foreign_billed': total_foreign_costs,
            'foreign_to_bill': 0.0,
        }

        if with_action and self.env.user.has_group('account.group_account_readonly'):
            costs['action'] = self._get_action_for_profitability_section(cost_ids, 'other_costs_aal')
            revenues['action'] = self._get_action_for_profitability_section(revenue_ids, 'other_revenues_aal')

        return {
            'revenues': {'data': [revenues], 'total': {'invoiced': total_revenues, 'to_invoice': 0.0, 'foreign_invoiced': total_foreign_revenues, 'foreign_to_invoice': 0.0}},
            'costs': {'data': [costs], 'total': {'billed': total_costs, 'to_bill': 0.0, 'foreign_billed': total_foreign_costs, 'foreign_to_bill': 0.0}},
        }

    # -------------------------------------------------------------------------
    # Purchase order foreign amounts
    # -------------------------------------------------------------------------
    def _get_purchase_order_foreign_amounts(self, purchase_lines):
        """Compute the foreign billed / to-bill amounts for purchase order lines.

        Mirrors the core monetary logic used for the local-currency amounts
        (``purchase_line_amount_to_invoice - total_invoiced``, considering
        posted and non-posted/non-cancel invoice lines) instead of prorating
        by ``qty_to_invoice``, so a quantity fully "invoiced" that still has a
        monetary gap (price/rate mismatches, credit notes) keeps showing the
        real pending amount instead of dropping to 0.

        :return: tuple (foreign_billed, foreign_to_bill) for the given lines,
            both negative as they represent costs.
        """
        foreign_billed = foreign_to_bill = 0.0
        for purchase_line in purchase_lines:
            contribution = sum(
                percentage for ids, percentage in purchase_line.analytic_distribution.items()
                if str(self.account_id.id) in ids.split(',')
            ) / 100.
            committed = (purchase_line.foreign_subtotal or 0.0) * contribution

            invoice_lines = purchase_line.invoice_lines.filtered(
                lambda l: l.parent_state != 'cancel'
                and l.analytic_distribution
                and any(str(self.account_id.id) in key.split(',') for key in l.analytic_distribution)
            )

            if not invoice_lines:
                foreign_to_bill -= committed
                continue

            total_invoiced = 0.0
            for line in invoice_lines:
                line_contribution = sum(
                    percentage for ids, percentage in line.analytic_distribution.items()
                    if str(self.account_id.id) in ids.split(',')
                ) / 100.
                cost = line.foreign_balance * line_contribution
                if line.move_id.move_type not in ('in_refund', 'out_refund'):
                    total_invoiced += cost
                if line.parent_state == 'posted':
                    foreign_billed -= cost
                else:
                    foreign_to_bill -= cost
            foreign_to_bill -= committed - total_invoiced

        return foreign_billed, foreign_to_bill

    # -------------------------------------------------------------------------
    # Main profitability items override
    # -------------------------------------------------------------------------
    def _get_profitability_items(self, with_action=True):
        """Compute the profitability items injecting the foreign currency amounts.

        The local currency values come from the core modules. The foreign
        amounts follow the same real-invoiced-amount criterion as the local
        currency for both the invoiced and to-invoice/to-bill columns (read
        from ``foreign_balance`` of the invoices), instead of prorating by
        quantity.
        """
        profitability_items = super()._get_profitability_items(with_action)

        # Ensure all totals have foreign keys initialized
        profitability_items['revenues']['total'].setdefault('foreign_to_invoice', 0.0)
        profitability_items['revenues']['total'].setdefault('foreign_invoiced', 0.0)
        profitability_items['costs']['total'].setdefault('foreign_to_bill', 0.0)
        profitability_items['costs']['total'].setdefault('foreign_billed', 0.0)

        # Ensure each data item has foreign keys
        for item in profitability_items['revenues']['data']:
            item.setdefault('foreign_to_invoice', 0.0)
            item.setdefault('foreign_invoiced', 0.0)
        for item in profitability_items['costs']['data']:
            item.setdefault('foreign_to_bill', 0.0)
            item.setdefault('foreign_billed', 0.0)

        # Handle purchase_order foreign amounts if present (from project_purchase)
        purchase_order_section = None
        for item in profitability_items['costs']['data']:
            if item['id'] == 'purchase_order':
                purchase_order_section = item
                break

        if purchase_order_section:
            purchase_lines = self.env['purchase.order.line'].sudo().search([
                ('analytic_distribution', 'in', self.account_id.ids),
                ('state', 'in', 'purchase')
            ])
            purchase_order_section['foreign_billed'], purchase_order_section['foreign_to_bill'] = (
                self._get_purchase_order_foreign_amounts(purchase_lines)
            )

        # Recalculate foreign totals by summing sections
        profitability_items['revenues']['total']['foreign_to_invoice'] = sum(
            s.get('foreign_to_invoice', 0.0) for s in profitability_items['revenues']['data']
        )
        profitability_items['revenues']['total']['foreign_invoiced'] = sum(
            s.get('foreign_invoiced', 0.0) for s in profitability_items['revenues']['data']
        )
        profitability_items['costs']['total']['foreign_to_bill'] = sum(
            s.get('foreign_to_bill', 0.0) for s in profitability_items['costs']['data']
        )
        profitability_items['costs']['total']['foreign_billed'] = sum(
            s.get('foreign_billed', 0.0) for s in profitability_items['costs']['data']
        )

        return profitability_items

    # -------------------------------------------------------------------------
    # get_panel_data: final injection point
    # -------------------------------------------------------------------------
    def get_panel_data(self):
        """Inject the foreign currency data into the profitability panel payload."""
        panel_data = super().get_panel_data()
        panel_data['foreign_currency_symbol'] = self._get_foreign_currency_symbol()
        panel_data['foreign_currency_id'] = self.company_id.foreign_currency_id.id
        return panel_data
