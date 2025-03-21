from odoo import models, fields, api, _
from odoo.tools.misc import get_lang
from ..tools.utils import get_is_foreign_currency
import logging
_logger = logging.getLogger(__name__)

class CashFlowReportCustomHandler(models.AbstractModel):
    _inherit = 'account.cash.flow.report.handler'
    
    def _compute_liquidity_balance(self, report, options, currency_table_query, payment_account_ids, date_scope):
        ''' Compute the balance of all liquidity accounts to populate the following sections:
            'Cash and cash equivalents, beginning of period' and 'Cash and cash equivalents, closing balance'.

        :param options:                 The report options.
        :param currency_table_query:    The custom query containing the multi-companies rates.
        :param payment_account_ids:     A tuple containing all account.account's ids being used in a liquidity journal.
        :return:                        A list of tuple (account_id, account_code, account_name, balance).
        '''
        queries = []
        params = []
        report_in_foreign_currency = get_is_foreign_currency(self.env)
        if self.pool['account.account'].name.translate:
            lang = self.env.user.lang or get_lang(self.env).code
            account_name = f"COALESCE(account_account.name->>'{lang}', account_account.name->>'en_US')"
        else:
            account_name = 'account_account.name'

        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            tables, where_clause, where_params = report._query_get(column_group_options, date_scope, domain=[('account_id', 'in', payment_account_ids)])

            queries.append(f'''
                SELECT
                    %s AS column_group_key,
                    account_move_line.account_id,
                    account_account.code AS account_code,
                    {account_name} AS account_name,
                    CASE WHEN {report_in_foreign_currency}
                    THEN (
                        SUM(ROUND(account_move_line.foreign_balance * currency_table.rate, currency_table.precision))
                    )
                    ELSE (
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision))
                    )
                    END as balance
                FROM {tables}
                JOIN account_account
                    ON account_account.id = account_move_line.account_id
                LEFT JOIN {currency_table_query}
                    ON currency_table.company_id = account_move_line.company_id
                WHERE {where_clause}
                GROUP BY account_move_line.account_id, account_account.code, {account_name}
            ''')

            params += [column_group_key, *where_params]

        self._cr.execute(' UNION ALL '.join(queries), params)

        return self._cr.dictfetchall()
    
    def _get_liquidity_moves(self, report, options, currency_table_query, payment_account_ids, payment_move_ids, cash_flow_tag_ids):
        ''' Fetch all information needed to compute lines from liquidity moves.
        The difficulty is to represent only the not-reconciled part of balance.

        :param options:                 The report options.
        :param currency_table_query:    The floating query to handle a multi-company/multi-currency environment.
        :param payment_move_ids:        A tuple containing all account.move's ids being the liquidity moves.
        :param payment_account_ids:     A tuple containing all account.account's ids being used in a liquidity journal.
        :return:                        A list of tuple (account_id, account_code, account_name, account_type, amount).
        '''
        if not payment_move_ids:
            return []
        report_in_foreign_currency = get_is_foreign_currency(self.env)
        reconciled_aml_groupby_account = {}

        queries = []
        params = []
        if self.pool['account.account'].name.translate:
            lang = self.env.user.lang or get_lang(self.env).code
            account_name = f"COALESCE(account_account.name->>'{lang}', account_account.name->>'en_US')"
        else:
            account_name = 'account_account.name'

        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            move_ids = self._get_move_ids_query(report, payment_account_ids, column_group_options)

            queries.append(f'''
                (WITH payment_move_ids AS ({move_ids})
                -- Credit amount of each account
                SELECT
                    %s AS column_group_key,
                    account_move_line.account_id,
                    account_account.code AS account_code,
                    {account_name} AS account_name,
                    account_account.account_type AS account_account_type,
                    account_account_account_tag.account_account_tag_id AS account_tag_id,
                    CASE WHEN {report_in_foreign_currency}
                    THEN (
                        SUM(ROUND(account_partial_reconcile.amount * account_partial_reconcile.credit_move_foreign_inverse_rate, currency_table.precision)) 
                    )
                    ELSE (
                        SUM(ROUND(account_partial_reconcile.amount * currency_table.rate, currency_table.precision)) 
                    )
                    END as balance
                FROM account_move_line
                LEFT JOIN {currency_table_query}
                    ON currency_table.company_id = account_move_line.company_id
                LEFT JOIN account_partial_reconcile
                    ON account_partial_reconcile.credit_move_id = account_move_line.id
                JOIN account_account
                    ON account_account.id = account_move_line.account_id
                LEFT JOIN account_account_account_tag
                    ON account_account_account_tag.account_account_id = account_move_line.account_id
                    AND account_account_account_tag.account_account_tag_id IN %s
                WHERE account_move_line.move_id IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                    AND account_move_line.account_id NOT IN %s
                    AND account_partial_reconcile.max_date BETWEEN %s AND %s
                GROUP BY account_move_line.company_id, account_move_line.account_id, account_account.code, {account_name}, account_account.account_type, account_account_account_tag.account_account_tag_id

                UNION ALL

                -- Debit amount of each account
                SELECT
                    %s AS column_group_key,
                    account_move_line.account_id,
                    account_account.code AS account_code,
                    {account_name} AS account_name,
                    account_account.account_type AS account_account_type,
                    account_account_account_tag.account_account_tag_id AS account_tag_id,
                    CASE WHEN {report_in_foreign_currency}
                    THEN (
                        -SUM(ROUND(account_partial_reconcile.amount * account_partial_reconcile.debit_move_foreign_inverse_rate, currency_table.precision)) 
                    )
                    ELSE (
                        -SUM(ROUND(account_partial_reconcile.amount * currency_table.rate, currency_table.precision)) 
                    )
                    END as balance
                FROM account_move_line
                LEFT JOIN {currency_table_query}
                    ON currency_table.company_id = account_move_line.company_id
                LEFT JOIN account_partial_reconcile
                    ON account_partial_reconcile.debit_move_id = account_move_line.id
                JOIN account_account
                    ON account_account.id = account_move_line.account_id
                LEFT JOIN account_account_account_tag
                    ON account_account_account_tag.account_account_id = account_move_line.account_id
                    AND account_account_account_tag.account_account_tag_id IN %s
                WHERE account_move_line.move_id IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                    AND account_move_line.account_id NOT IN %s
                    AND account_partial_reconcile.max_date BETWEEN %s AND %s
                GROUP BY account_move_line.company_id, account_move_line.account_id, account_account.code, {account_name}, account_account.account_type, account_account_account_tag.account_account_tag_id

                UNION ALL

                -- Total amount of each account
                SELECT
                    %s AS column_group_key,
                    account_move_line.account_id AS account_id,
                    account_account.code AS account_code,
                    {account_name} AS account_name,
                    account_account.account_type AS account_account_type,
                    account_account_account_tag.account_account_tag_id AS account_tag_id,
                    CASE WHEN {report_in_foreign_currency}
                    THEN (
                        SUM(ROUND(account_move_line.foreign_balance * currency_table.rate, currency_table.precision))
                    )
                    ELSE (
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision))
                    )
                    END as balance
                FROM account_move_line
                LEFT JOIN {currency_table_query}
                    ON currency_table.company_id = account_move_line.company_id
                JOIN account_account
                    ON account_account.id = account_move_line.account_id
                LEFT JOIN account_account_account_tag
                    ON account_account_account_tag.account_account_id = account_move_line.account_id
                    AND account_account_account_tag.account_account_tag_id IN %s
                WHERE account_move_line.move_id IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                    AND account_move_line.account_id NOT IN %s
                GROUP BY account_move_line.account_id, account_account.code, {account_name}, account_account.account_type, account_account_account_tag.account_account_tag_id)
            ''')

            date_from = column_group_options['date']['date_from']
            date_to = column_group_options['date']['date_to']

            params += [
                column_group_key, tuple(cash_flow_tag_ids), payment_account_ids, date_from, date_to,
                column_group_key, tuple(cash_flow_tag_ids), payment_account_ids, date_from, date_to,
                column_group_key, tuple(cash_flow_tag_ids), payment_account_ids,
            ]

        self._cr.execute(' UNION ALL '.join(queries), params)

        for aml_data in self._cr.dictfetchall():
            reconciled_aml_groupby_account.setdefault(aml_data['account_id'], {})
            reconciled_aml_groupby_account[aml_data['account_id']].setdefault(aml_data['column_group_key'], {
                'column_group_key': aml_data['column_group_key'],
                'account_id': aml_data['account_id'],
                'account_code': aml_data['account_code'],
                'account_name': aml_data['account_name'],
                'account_account_type': aml_data['account_account_type'],
                'account_tag_id': aml_data['account_tag_id'],
                'balance': 0.0,
            })

            reconciled_aml_groupby_account[aml_data['account_id']][aml_data['column_group_key']]['balance'] -= aml_data['balance']

        return list(reconciled_aml_groupby_account.values())

    def _get_reconciled_moves(self, report, options, currency_table_query, payment_account_ids, payment_move_ids, cash_flow_tag_ids):
        ''' Retrieve all moves being not a liquidity move to be shown in the cash flow statement.
        Each amount must be valued at the percentage of what is actually paid.
        E.g. An invoice of 1000 being paid at 50% must be valued at 500.

        :param options:                 The report options.
        :param currency_table_query:    The floating query to handle a multi-company/multi-currency environment.
        :param payment_move_ids:        A tuple containing all account.move's ids being the liquidity moves.
        :param payment_account_ids:     A tuple containing all account.account's ids being used in a liquidity journal.
        :return:                        A list of tuple (account_id, account_code, account_name, account_type, amount).
        '''
        if not payment_move_ids:
            return []

        reconciled_account_ids = {column_group_key: set() for column_group_key in options['column_groups']}
        reconciled_percentage_per_move = {column_group_key: {} for column_group_key in options['column_groups']}
        report_in_foreign_currency = get_is_foreign_currency(self.env)
        queries = []
        params = []

        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            move_ids = self._get_move_ids_query(report, payment_account_ids, column_group_options)

            queries.append(f'''
                (WITH payment_move_ids AS ({move_ids})
                SELECT
                    %s AS column_group_key,
                    debit_line.move_id,
                    debit_line.account_id,
                    CASE WHEN {report_in_foreign_currency}
                    THEN (
                        SUM(ROUND(account_partial_reconcile.amount * account_partial_reconcile.debit_move_foreign_inverse_rate))
                    )
                    ELSE (
                        SUM(account_partial_reconcile.amount)
                    )
                    END as balance
                    
                FROM account_move_line AS credit_line
                LEFT JOIN account_partial_reconcile
                    ON account_partial_reconcile.credit_move_id = credit_line.id
                INNER JOIN account_move_line AS debit_line
                    ON debit_line.id = account_partial_reconcile.debit_move_id
                WHERE credit_line.move_id IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                    AND credit_line.account_id NOT IN %s
                    AND credit_line.credit > 0.0
                    AND debit_line.move_id NOT IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                    AND account_partial_reconcile.max_date BETWEEN %s AND %s
                GROUP BY debit_line.move_id, debit_line.account_id

                UNION ALL

                SELECT
                    %s AS column_group_key,
                    credit_line.move_id,
                    credit_line.account_id,
                    CASE WHEN {report_in_foreign_currency}
                    THEN (
                        -SUM(ROUND(account_partial_reconcile.amount * account_partial_reconcile.credit_move_foreign_inverse_rate))
                    )
                    ELSE (
                        -SUM(account_partial_reconcile.amount)
                    )
                    END as balance
                FROM account_move_line AS debit_line
                LEFT JOIN account_partial_reconcile
                    ON account_partial_reconcile.debit_move_id = debit_line.id
                INNER JOIN account_move_line AS credit_line
                    ON credit_line.id = account_partial_reconcile.credit_move_id
                WHERE debit_line.move_id IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                    AND debit_line.account_id NOT IN %s
                    AND debit_line.debit > 0.0
                    AND credit_line.move_id NOT IN (SELECT unnest(payment_move_ids.move_id) FROM payment_move_ids)
                    AND account_partial_reconcile.max_date BETWEEN %s AND %s
                GROUP BY credit_line.move_id, credit_line.account_id)
            ''')

            params += [
                column_group_key,
                payment_account_ids,
                column_group_options['date']['date_from'],
                column_group_options['date']['date_to'],
            ] * 2

        self._cr.execute(' UNION ALL '.join(queries), params)

        for aml_data in self._cr.dictfetchall():
            reconciled_percentage_per_move[aml_data['column_group_key']].setdefault(aml_data['move_id'], {})
            reconciled_percentage_per_move[aml_data['column_group_key']][aml_data['move_id']].setdefault(aml_data['account_id'], [0.0, 0.0])
            reconciled_percentage_per_move[aml_data['column_group_key']][aml_data['move_id']][aml_data['account_id']][0] += aml_data['balance']

            reconciled_account_ids[aml_data['column_group_key']].add(aml_data['account_id'])

        if not reconciled_percentage_per_move:
            return []

        queries = []
        params = []

        for column in options['columns']:
            queries.append(f'''
                SELECT
                    %s AS column_group_key,
                    account_move_line.move_id,
                    account_move_line.account_id,
                    CASE WHEN {report_in_foreign_currency}
                    THEN (
                        SUM(account_move_line.foreign_balance)
                    )
                    ELSE (
                        SUM(account_move_line.balance)
                    )
                    END as balance
                FROM account_move_line
                JOIN {currency_table_query}
                    ON currency_table.company_id = account_move_line.company_id
                WHERE account_move_line.move_id IN %s
                    AND account_move_line.account_id IN %s
                GROUP BY account_move_line.move_id, account_move_line.account_id
            ''')

            params += [column['column_group_key'], tuple(reconciled_percentage_per_move[column['column_group_key']].keys()) or (None,), tuple(reconciled_account_ids[column['column_group_key']]) or (None,)]

        self._cr.execute(' UNION ALL '.join(queries), params)

        for aml_data in self._cr.dictfetchall():
            if aml_data['account_id'] in reconciled_percentage_per_move[aml_data['column_group_key']][aml_data['move_id']]:
                reconciled_percentage_per_move[aml_data['column_group_key']][aml_data['move_id']][aml_data['account_id']][1] += aml_data['balance']

        reconciled_aml_per_account = {}

        queries = []
        params = []
        if self.pool['account.account'].name.translate:
            lang = self.env.user.lang or get_lang(self.env).code
            account_name = f"COALESCE(account_account.name->>'{lang}', account_account.name->>'en_US')"
        else:
            account_name = 'account_account.name'

        for column in options['columns']:
            queries.append(f'''
                SELECT
                    %s AS column_group_key,
                    account_move_line.move_id,
                    account_move_line.account_id,
                    account_account.code AS account_code,
                    {account_name} AS account_name,
                    account_account.account_type AS account_account_type,
                    account_account_account_tag.account_account_tag_id AS account_tag_id,
                    CASE WHEN {report_in_foreign_currency}
                    THEN (
                        SUM(ROUND(account_move_line.foreign_balance * currency_table.rate, currency_table.precision))
                    )
                    ELSE (
                        SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision))
                    )
                    END as balance
                    
                FROM account_move_line
                LEFT JOIN {currency_table_query}
                    ON currency_table.company_id = account_move_line.company_id
                JOIN account_account
                    ON account_account.id = account_move_line.account_id
                LEFT JOIN account_account_account_tag
                    ON account_account_account_tag.account_account_id = account_move_line.account_id
                    AND account_account_account_tag.account_account_tag_id IN %s
                WHERE account_move_line.move_id IN %s
                GROUP BY account_move_line.move_id, account_move_line.account_id, account_account.code, {account_name}, account_account.account_type, account_account_account_tag.account_account_tag_id
            ''')

            params += [column['column_group_key'], tuple(cash_flow_tag_ids), tuple(reconciled_percentage_per_move[column['column_group_key']].keys()) or (None,)]

        self._cr.execute(' UNION ALL '.join(queries), params)

        for aml_data in self._cr.dictfetchall():
            aml_column_group_key = aml_data['column_group_key']
            aml_move_id = aml_data['move_id']
            aml_account_id = aml_data['account_id']
            aml_account_code = aml_data['account_code']
            aml_account_name = aml_data['account_name']
            aml_account_account_type = aml_data['account_account_type']
            aml_account_tag_id = aml_data['account_tag_id']
            aml_balance = aml_data['balance']

            # Compute the total reconciled for the whole move.
            total_reconciled_amount = 0.0
            total_amount = 0.0

            for reconciled_amount, amount in reconciled_percentage_per_move[aml_column_group_key][aml_move_id].values():
                total_reconciled_amount += reconciled_amount
                total_amount += amount

            # Compute matched percentage for each account.
            if total_amount and aml_account_id not in reconciled_percentage_per_move[aml_column_group_key][aml_move_id]:
                # Lines being on reconciled moves but not reconciled with any liquidity move must be valued at the
                # percentage of what is actually paid.
                reconciled_percentage = total_reconciled_amount / total_amount
                aml_balance *= reconciled_percentage
            elif not total_amount and aml_account_id in reconciled_percentage_per_move[aml_column_group_key][aml_move_id]:
                # The total amount to reconcile is 0. In that case, only add entries being on these accounts. Otherwise,
                # this special case will lead to an unexplained difference equivalent to the reconciled amount on this
                # account.
                # E.g:
                #
                # Liquidity move:
                # Account         | Debit     | Credit
                # --------------------------------------
                # Bank            |           | 100
                # Receivable      | 100       |
                #
                # Reconciled move:                          <- reconciled_amount=100, total_amount=0.0
                # Account         | Debit     | Credit
                # --------------------------------------
                # Receivable      |           | 200
                # Receivable      | 200       |             <- Only the reconciled part of this entry must be added.
                aml_balance = -reconciled_percentage_per_move[aml_column_group_key][aml_move_id][aml_account_id][0]
            else:
                # Others lines are not considered.
                continue

            reconciled_aml_per_account.setdefault(aml_account_id, {})
            reconciled_aml_per_account[aml_account_id].setdefault(aml_column_group_key, {
                'column_group_key': aml_column_group_key,
                'account_id': aml_account_id,
                'account_code': aml_account_code,
                'account_name': aml_account_name,
                'account_account_type': aml_account_account_type,
                'account_tag_id': aml_account_tag_id,
                'balance': 0.0,
            })

            reconciled_aml_per_account[aml_account_id][aml_column_group_key]['balance'] -= aml_balance

        return list(reconciled_aml_per_account.values())

    