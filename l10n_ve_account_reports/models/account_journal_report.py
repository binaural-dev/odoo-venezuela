from odoo import models, _
from collections import defaultdict
from ..tools.utils import get_is_foreign_currency


class JournalReportCustomHandler(models.AbstractModel):
    _inherit = 'account.journal.report.handler'

    def _query_aml(self, options, offset=0, journal=False):
        params = []
        queries = []
        report_in_foreign_currency = get_is_foreign_currency(self.env)
        lang = self.env.user.lang or get_lang(self.env).code
        acc_name = f"COALESCE(acc.name->>'{lang}', acc.name->>'en_US')" if \
            self.pool['account.account'].name.translate else 'acc.name'
        j_name = f"COALESCE(j.name->>'{lang}', j.name->>'en_US')" if \
            self.pool['account.journal'].name.translate else 'j.name'
        tax_name = f"COALESCE(tax.name->>'{lang}', tax.name->>'en_US')" if \
            self.pool['account.tax'].name.translate else 'tax.name'
        tag_name = f"COALESCE(tag.name->>'{lang}', tag.name->>'en_US')" if \
            self.pool['account.account.tag'].name.translate else 'tag.name'
        report = self.env.ref('account_reports.journal_report')
        for column_group_key, options_group in report._split_options_per_column_group(options).items():
            # Override any forced options: We want the ones given in the options
            options_group['date'] = options['date']
            tables, where_clause, where_params = report._query_get(options_group, 'strict_range', domain=[('journal_id', '=', journal.id)])
            sort_by_date = options_group.get('sort_by_date')
            params.append(column_group_key)
            params += where_params

            limit_to_load = report.load_more_limit + 1 if report.load_more_limit and not self._context.get('print_mode') else None

            params += [limit_to_load, offset]
            queries.append(f"""
                SELECT
                    %s AS column_group_key,
                    "account_move_line".id as move_line_id,
                    "account_move_line".name,
                    "account_move_line".amount_currency,
                    "account_move_line".tax_base_amount,
                    "account_move_line".currency_id as move_line_currency,
                    "account_move_line".amount_currency,
                    am.id as move_id,
                    am.name as move_name,
                    am.journal_id,
                    am.date,
                    am.currency_id as move_currency,
                    am.amount_total_in_currency_signed as amount_currency_total,
                    am.currency_id != cp.currency_id as is_multicurrency,
                    p.name as partner_name,
                    acc.code as account_code,
                    {acc_name} as account_name,
                    acc.account_type as account_type,
                    CASE WHEN {report_in_foreign_currency}
                    THEN (
                        COALESCE("account_move_line".foreign_debit, 0)
                    )
                    ELSE (
                        COALESCE("account_move_line".debit, 0)
                    )
                    END as debit,
                    CASE WHEN {report_in_foreign_currency}
                    THEN (
                        COALESCE("account_move_line".foreign_credit, 0)
                    )
                    ELSE (
                        COALESCE("account_move_line".credit, 0)
                    )
                    END as credit,
                    CASE WHEN {report_in_foreign_currency}
                    THEN (
                        COALESCE("account_move_line".foreign_balance, 0)
                    )
                    ELSE (
                        COALESCE("account_move_line".balance, 0)
                    )
                    END as balance,
                    {j_name} as journal_name,
                    j.code as journal_code,
                    j.type as journal_type,
                    j.currency_id as journal_currency,
                    journal_curr.name as journal_currency_name,
                    cp.currency_id as company_currency,
                    CASE WHEN j.type = 'sale' THEN am.payment_reference WHEN j.type = 'purchase' THEN am.ref ELSE '' END as reference,
                    array_remove(array_agg(DISTINCT {tax_name}), NULL) as taxes,
                    array_remove(array_agg(DISTINCT {tag_name}), NULL) as tax_grids
                    
                FROM {tables}
                JOIN account_move am ON am.id = "account_move_line".move_id
                JOIN account_account acc ON acc.id = "account_move_line".account_id
                LEFT JOIN res_partner p ON p.id = "account_move_line".partner_id
                JOIN account_journal j ON j.id = am.journal_id
                JOIN res_company cp ON cp.id = am.company_id
                LEFT JOIN account_move_line_account_tax_rel aml_at_rel ON aml_at_rel.account_move_line_id = "account_move_line".id
                LEFT JOIN account_tax parent_tax ON parent_tax.id = aml_at_rel.account_tax_id and parent_tax.amount_type = 'group'
                LEFT JOIN account_tax_filiation_rel tax_filiation_rel ON tax_filiation_rel.parent_tax = parent_tax.id
                LEFT JOIN account_tax tax ON (tax.id = aml_at_rel.account_tax_id and tax.amount_type != 'group') or tax.id = tax_filiation_rel.child_tax
                LEFT JOIN account_account_tag_account_move_line_rel tag_rel ON tag_rel.account_move_line_id = "account_move_line".id
                LEFT JOIN account_account_tag tag on tag_rel.account_account_tag_id = tag.id
                LEFT JOIN res_currency journal_curr on journal_curr.id = j.currency_id
                WHERE {where_clause}
                GROUP BY "account_move_line".id, am.id, p.id, acc.id, j.id, cp.id, journal_curr.id
                ORDER BY j.id, CASE when am.name = '/' then 1 else 0 end,
                {" am.date, am.name," if sort_by_date else " am.name , am.date,"}
                CASE acc.account_type
                    WHEN 'liability_payable' THEN 1
                    WHEN 'asset_receivable' THEN 1
                    WHEN 'liability_credit_card' THEN 5
                    WHEN 'asset_cash' THEN 5
                    ELSE 2
               END,
               "account_move_line".tax_line_id NULLS FIRST
               LIMIT %s
               OFFSET %s
            """)

        # 1.2.Fetch data from DB
        rslt = {}
        self._cr.execute('(' + ') UNION ALL ('.join(queries) + ')', params)
        for aml_result in self._cr.dictfetchall():
            rslt.setdefault(aml_result['move_line_id'], {col_group_key: {} for col_group_key in options['column_groups']})
            rslt[aml_result['move_line_id']][aml_result['column_group_key']] = aml_result

        return rslt

    def _get_move_line_additional_col(self, options, current_balance, values, is_unreconciled_payment):
        """ Returns the additional columns to be displayed on an account move line.
        These are the column coming after the debit and credit columns.
        For a sale or purchase journal, they will contain the taxes' information.
        For a bank journal, they will contain the cumulated amount.

        :param current_balance: The current balance of the move line, if any.
        :param values: The values of the move line.
        """
        report = self.env['account.report']
        report_in_foreign_currency = get_is_foreign_currency(self.env)
        additional_col = [
            {'name': ''},
            {'name': ''},
        ]
        if values['journal_type'] in ['sale', 'purchase']:
            tax_val = ''
            if values['taxes']:
                # Display the taxes affecting the line, formatted as such: "T: t1, t2"
                tax_val = _('T: %s', ', '.join(values['taxes']))
            elif values['tax_base_amount'] and not report_in_foreign_currency:
                # Display the base amount on wich this tax line is based off, formatted as such: "B: $0.0"
                tax_val = _('B: %s', report.format_value(values['tax_base_amount'], blank_if_zero=False, figure_type='monetary'))
            elif values['tax_base_amount'] and report_in_foreign_currency:
                # Display the base amount on wich this tax line is based off, formatted as such: "B: $0.0"
                tax_val = _('B: %s', report.format_value(values['debit'], blank_if_zero=False, figure_type='monetary'))
            values['tax_grids'] = values['tax_grids']
            additional_col = [
                {'name': tax_val, 'class': 'text-start'},
                {'name': ', '.join(values['tax_grids'])},
            ]
        elif values['journal_type'] == 'bank':
            if values['account_type'] not in ('liability_credit_card', 'asset_cash') and current_balance:
                additional_col = [
                    {
                        'name': report.format_value(current_balance, figure_type='monetary'),
                        'no_format': current_balance,
                        'class': 'number',
                    },
                    {'name': ''},
                ]
            if self.user_has_groups('base.group_multi_currency') and values['move_line_currency'] != values['company_currency']:
                amount = -values['amount_currency'] if not is_unreconciled_payment else values['amount_currency']
                additional_col[-1] = {
                    'name': report.format_value(amount, currency=self.env['res.currency'].browse(values['move_line_currency']), figure_type='monetary'),
                    'no_format': amount,
                    'class': 'number',
                }
        return additional_col

    def _get_generic_tax_summary_for_sections(self, options, data):
        """
        Overridden to make use of the generic tax report computation
        Works by forcing specific options into the tax report to only get the lines we need.
        The result is grouped by the country in which the tag exists in case of multivat environment.
        Returns a dictionary with the following structure:
        {
            Country : [
                {name, base_amount, tax_amount},
                {name, base_amount, tax_amount},
                {name, base_amount, tax_amount},
                ...
            ],
            Country : [
                {name, base_amount, tax_amount},
                {name, base_amount, tax_amount},
                {name, base_amount, tax_amount},
                ...
            ],
            ...
        }
        """
        report = self.env['account.report']
        tax_report_options = self._get_generic_tax_report_options(options, data)
        tax_report = self.env.ref('account.generic_tax_report')
        tax_report_lines = tax_report._get_lines(tax_report_options)

        tax_values = {}
        for tax_report_line in tax_report_lines:
            model, line_id = report._parse_line_id(tax_report_line.get('id'))[-1][1:]
            if model == 'account.tax':
                tax_values[line_id] = {
                    'base_amount': tax_report_line['columns'][0]['no_format'],
                    'tax_amount': tax_report_line['columns'][1]['no_format'],
                }

        # Make the final data dict that will be used by the template, using the taxes information.
        taxes = self.env['account.tax'].browse(tax_values.keys())
        res = defaultdict(list)
        for tax in taxes:
            res[tax.country_id.name].append({
                'base_amount': report.format_value(tax_values[tax.id]['base_amount'], blank_if_zero=False, figure_type='monetary'),
                'tax_amount': report.format_value(tax_values[tax.id]['tax_amount'], blank_if_zero=False, figure_type='monetary'),
                'name': tax.name,
                'line_id': report._get_generic_line_id('account.tax', tax.id)
            })

        # Return the result, ordered by country name
        return dict(sorted(res.items()))
    
    def _get_journal_initial_balance(self, options, journal_id, date_month=False):
        queries = []
        params = []
        report = self.env.ref('account_reports.journal_report')
        report_in_foreign_currency = get_is_foreign_currency(self.env)
        for column_group_key, options_group in report._split_options_per_column_group(options).items():
            new_options = self.env['account.general.ledger.report.handler']._get_options_initial_balance(options_group)  # Same options as the general ledger
            tables, where_clause, where_params = report._query_get(new_options, 'normal', domain=[('journal_id', '=', journal_id)])
            params.append(column_group_key)
            params += where_params
            queries.append(f"""
                SELECT
                    %s AS column_group_key,
                    CASE WHEN {report_in_foreign_currency}
                    THEN (
                        sum("account_move_line".foreign_balance) 
                    )
                    ELSE (
                        sum("account_move_line".balance) 
                    )
                    END as balance
                FROM {tables}
                JOIN account_journal journal ON journal.id = "account_move_line".journal_id AND "account_move_line".account_id = journal.default_account_id
                WHERE {where_clause}
                GROUP BY journal.id
            """)

        self._cr.execute(" UNION ALL ".join(queries), params)

        init_balance_by_col_group = {column_group_key: 0.0 for column_group_key in options['column_groups']}
        for result in self._cr.dictfetchall():
            init_balance_by_col_group[result['column_group_key']] = result['balance']

        return init_balance_by_col_group