from odoo import models, api
from collections import defaultdict
from ..tools.utils import get_is_foreign_currency


class GenericTaxReportCustomHandler(models.AbstractModel):
    _inherit = 'account.generic.tax.report.handler'


    # -------------------------------------------------------------------------
    # GENERIC TAX REPORT COMPUTATION (DYNAMIC LINES)
    # -------------------------------------------------------------------------

    @api.model
    def _read_generic_tax_report_amounts_no_tax_details(self, report, options, options_by_column_group):
        # Fetch the group of taxes.
        # If all child taxes have a 'none' type_tax_use, all amounts are aggregated and only the group appears on the report.
        self._cr.execute(
            '''
                SELECT
                    group_tax.id,
                    group_tax.type_tax_use,
                    ARRAY_AGG(child_tax.id) AS child_tax_ids,
                    ARRAY_AGG(DISTINCT child_tax.type_tax_use) AS child_types
                FROM account_tax_filiation_rel group_tax_rel
                JOIN account_tax group_tax ON group_tax.id = group_tax_rel.parent_tax
                JOIN account_tax child_tax ON child_tax.id = group_tax_rel.child_tax
                WHERE group_tax.amount_type = 'group' AND group_tax.company_id IN %s
                GROUP BY group_tax.id
            ''',
            [tuple(comp['id'] for comp in options.get('multi_company', self.env.company))],
        )
        group_of_taxes_info = {}
        child_to_group_of_taxes = {}
        report_in_foreign_currency = get_is_foreign_currency(self.env)
        for row in self._cr.dictfetchall():
            row['to_expand'] = row['child_types'] != ['none']
            group_of_taxes_info[row['id']] = row
            for child_id in row['child_tax_ids']:
                child_to_group_of_taxes[child_id] = row['id']

        results = defaultdict(lambda: {  # key: type_tax_use
            'base_amount': {column_group_key: 0.0 for column_group_key in options['column_groups']},
            'tax_amount': {column_group_key: 0.0 for column_group_key in options['column_groups']},
            'children': defaultdict(lambda: {  # key: tax_id
                'base_amount': {column_group_key: 0.0 for column_group_key in options['column_groups']},
                'tax_amount': {column_group_key: 0.0 for column_group_key in options['column_groups']},
            }),
        })

        for column_group_key, options in options_by_column_group.items():
            tables, where_clause, where_params = report._query_get(options, 'strict_range')

            # Fetch the base amounts.
            self._cr.execute(f'''
                SELECT
                    tax.id AS tax_id,
                    tax.type_tax_use AS tax_type_tax_use,
                    src_group_tax.id AS src_group_tax_id,
                    src_group_tax.type_tax_use AS src_group_tax_type_tax_use,
                    src_tax.id AS src_tax_id,
                    src_tax.type_tax_use AS src_tax_type_tax_use,
                    CASE WHEN {report_in_foreign_currency}
                    THEN (
                        SUM(account_move_line.foreign_debit)
                    )
                    ELSE (
                        SUM(account_move_line.debit)
                    )
                    END AS base_amount
                FROM {tables}
                JOIN account_move_line_account_tax_rel tax_rel ON account_move_line.id = tax_rel.account_move_line_id
                JOIN account_tax tax ON tax.id = tax_rel.account_tax_id
                LEFT JOIN account_tax src_tax ON src_tax.id = account_move_line.tax_line_id
                LEFT JOIN account_tax src_group_tax ON src_group_tax.id = account_move_line.group_tax_id
                WHERE {where_clause}
                    AND (
                        /* CABA */
                        account_move_line__move_id.always_tax_exigible
                        OR account_move_line__move_id.tax_cash_basis_rec_id IS NOT NULL
                        OR tax.tax_exigibility != 'on_payment'
                    )
                    AND (
                        (
                            /* Tax lines affecting the base of others. */
                            account_move_line.tax_line_id IS NOT NULL
                            AND (
                                src_tax.type_tax_use IN ('sale', 'purchase')
                                OR src_group_tax.type_tax_use IN ('sale', 'purchase')
                            )
                        )
                        OR
                        (
                            /* For regular base lines. */
                            account_move_line.tax_line_id IS NULL
                            AND tax.type_tax_use IN ('sale', 'purchase')
                        )
                    )
                GROUP BY tax.id, src_group_tax.id, src_tax.id
                ORDER BY src_group_tax.sequence, src_group_tax.id, src_tax.sequence, src_tax.id, tax.sequence, tax.id
            ''', where_params)

            group_of_taxes_with_extra_base_amount = set()
            for row in self._cr.dictfetchall():
                is_tax_line = bool(row['src_tax_id'])
                if is_tax_line:
                    if row['src_group_tax_id'] \
                            and not group_of_taxes_info[row['src_group_tax_id']]['to_expand'] \
                            and row['tax_id'] in group_of_taxes_info[row['src_group_tax_id']]['child_tax_ids']:
                        # Suppose a base of 1000 with a group of taxes 20% affect + 10%.
                        # The base of the group of taxes must be 1000, not 1200 because the group of taxes is not
                        # expanded. So the tax lines affecting the base of its own group of taxes are ignored.
                        pass
                    elif row['tax_type_tax_use'] == 'none' and child_to_group_of_taxes.get(row['tax_id']):
                        # The tax line is affecting the base of a 'none' tax belonging to a group of taxes.
                        # In that case, the amount is accounted as an extra base for that group. However, we need to
                        # account it only once.
                        # For example, suppose a tax 10% affect base of subsequent followed by a group of taxes
                        # 20% + 30%. On a base of 1000.0, the tax line for 10% will affect the base of 20% + 30%.
                        # However, this extra base must be accounted only once since the base of the group of taxes
                        # must be 1100.0 and not 1200.0.
                        group_tax_id = child_to_group_of_taxes[row['tax_id']]
                        if group_tax_id not in group_of_taxes_with_extra_base_amount:
                            group_tax_info = group_of_taxes_info[group_tax_id]
                            results[group_tax_info['type_tax_use']]['children'][group_tax_id]['base_amount'][column_group_key] += row['base_amount']
                            group_of_taxes_with_extra_base_amount.add(group_tax_id)
                    else:
                        tax_type_tax_use = row['src_group_tax_type_tax_use'] or row['src_tax_type_tax_use']
                        results[tax_type_tax_use]['children'][row['tax_id']]['base_amount'][column_group_key] += row['base_amount']
                else:
                    if row['tax_id'] in group_of_taxes_info and group_of_taxes_info[row['tax_id']]['to_expand']:
                        # Expand the group of taxes since it contains at least one tax with a type != 'none'.
                        group_info = group_of_taxes_info[row['tax_id']]
                        for child_tax_id in group_info['child_tax_ids']:
                            results[group_info['type_tax_use']]['children'][child_tax_id]['base_amount'][column_group_key] += row['base_amount']
                    else:
                        if row['base_amount'] is not None:
                            row['base_amount'] = 0.0
                            results[row['tax_type_tax_use']]['children'][row['tax_id']]['base_amount'][column_group_key] += row['base_amount']
            # Fetch the tax amounts.
            self._cr.execute(f'''
                SELECT
                    tax.id AS tax_id,
                    tax.type_tax_use AS tax_type_tax_use,
                    group_tax.id AS group_tax_id,
                    group_tax.type_tax_use AS group_tax_type_tax_use,
                    CASE WHEN {report_in_foreign_currency}
                    THEN (
                        SUM(account_move_line.foreign_balance)
                    )
                    ELSE (
                        SUM(account_move_line.balance)
                    )
                    END AS tax_amount
                    
                FROM {tables}
                JOIN account_tax tax ON tax.id = account_move_line.tax_line_id
                LEFT JOIN account_tax group_tax ON group_tax.id = account_move_line.group_tax_id
                WHERE {where_clause}
                    AND (
                        /* CABA */
                        account_move_line__move_id.always_tax_exigible
                        OR account_move_line__move_id.tax_cash_basis_rec_id IS NOT NULL
                        OR tax.tax_exigibility != 'on_payment'
                    )
                    AND (
                        (group_tax.id IS NULL AND tax.type_tax_use IN ('sale', 'purchase'))
                        OR
                        (group_tax.id IS NOT NULL AND group_tax.type_tax_use IN ('sale', 'purchase'))
                    )
                GROUP BY tax.id, group_tax.id
            ''', where_params)

            for row in self._cr.dictfetchall():
                # Manage group of taxes.
                # In case the group of taxes is mixing multiple taxes having a type_tax_use != 'none', consider
                # them instead of the group.
                tax_id = row['tax_id']
                if row['group_tax_id']:
                    tax_type_tax_use = row['group_tax_type_tax_use']
                    if not group_of_taxes_info[row['group_tax_id']]['to_expand']:
                        tax_id = row['group_tax_id']
                else:
                    tax_type_tax_use = row['group_tax_type_tax_use'] or row['tax_type_tax_use']

                results[tax_type_tax_use]['tax_amount'][column_group_key] += row['tax_amount']
                results[tax_type_tax_use]['children'][tax_id]['tax_amount'][column_group_key] += row['tax_amount']

        return results