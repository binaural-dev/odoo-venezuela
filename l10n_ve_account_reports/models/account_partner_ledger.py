from odoo import models, _


class PartnerLedgerCustomHandler(models.AbstractModel):
    _inherit = "account.partner.ledger.report.handler"

    def _get_query_sums(self, options):
        params = []
        queries = []
        report = self.env.ref("account_reports.partner_ledger_report")

        amounts_query = self._get_sums_amount_rows_query()

        # Create the currency table.
        ct_query = self.env["res.currency"]._get_query_currency_table(options)
        for column_group_key, column_group_options in report._split_options_per_column_group(
            options
        ).items():
            tables, where_clause, where_params = report._query_get(column_group_options, "normal")
            params.append(column_group_key)
            params += where_params
            queries.append(
                f"""
                SELECT
                    account_move_line.partner_id                                                          AS groupby,
                    %s                                                                                    AS column_group_key,
                    {amounts_query}
                FROM {tables}
                LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                WHERE {where_clause}
                GROUP BY account_move_line.partner_id
            """
            )

        return " UNION ALL ".join(queries), params

    def _get_initial_balance_values(self, partner_ids, options):
        """
        Ensures the amounts of the query are on the currency that it should be (wheter it is USD
        or VEF).
        """
        queries = []
        params = []
        report = self.env.ref("account_reports.partner_ledger_report")
        ct_query = self.env["res.currency"]._get_query_currency_table(options)

        # Getting the string with the rows of the amounts
        amounts_query = self._get_sums_amount_rows_query()

        for column_group_key, column_group_options in report._split_options_per_column_group(
            options
        ).items():
            # Get sums for the initial balance.
            # period: [('date' <= options['date_from'] - 1)]
            new_options = self._get_options_initial_balance(column_group_options)
            tables, where_clause, where_params = report._query_get(
                new_options, "normal", domain=[("partner_id", "in", partner_ids)]
            )
            params.append(column_group_key)
            params += where_params
            queries.append(
                f"""
                SELECT
                    account_move_line.partner_id,
                    %s                                                                                    AS column_group_key,
                    {amounts_query}
                FROM {tables}
                LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                WHERE {where_clause}
                GROUP BY account_move_line.partner_id
            """
            )

        self._cr.execute(" UNION ALL ".join(queries), params)

        init_balance_by_col_group = {
            partner_id: {column_group_key: {} for column_group_key in options["column_groups"]}
            for partner_id in partner_ids
        }
        for result in self._cr.dictfetchall():
            init_balance_by_col_group[result["partner_id"]][result["column_group_key"]] = result

        return init_balance_by_col_group

    def _get_aml_values(self, options, partner_ids, offset=0, limit=None):
        rslt = {partner_id: [] for partner_id in partner_ids}

        amounts_query = self._get_amount_rows_query()

        partner_ids_wo_none = [x for x in partner_ids if x]
        directly_linked_aml_partner_clauses = []
        directly_linked_aml_partner_params = []
        indirectly_linked_aml_partner_params = []
        indirectly_linked_aml_partner_clause = "aml_with_partner.partner_id IS NOT NULL"
        if None in partner_ids:
            directly_linked_aml_partner_clauses.append("account_move_line.partner_id IS NULL")
        if partner_ids_wo_none:
            directly_linked_aml_partner_clauses.append("account_move_line.partner_id IN %s")
            directly_linked_aml_partner_params.append(tuple(partner_ids_wo_none))
            indirectly_linked_aml_partner_clause = "aml_with_partner.partner_id IN %s"
            indirectly_linked_aml_partner_params.append(tuple(partner_ids_wo_none))
        directly_linked_aml_partner_clause = (
            "(" + " OR ".join(directly_linked_aml_partner_clauses) + ")"
        )

        ct_query = self.env["res.currency"]._get_query_currency_table(options)
        queries = []
        all_params = []
        lang = self.env.lang or get_lang(self.env).code
        journal_name = (
            f"COALESCE(journal.name->>'{lang}', journal.name->>'en_US')"
            if self.pool["account.journal"].name.translate
            else "journal.name"
        )
        account_name = (
            f"COALESCE(account.name->>'{lang}', account.name->>'en_US')"
            if self.pool["account.account"].name.translate
            else "account.name"
        )
        report = self.env.ref("account_reports.partner_ledger_report")
        for column_group_key, group_options in report._split_options_per_column_group(
            options
        ).items():
            tables, where_clause, where_params = report._query_get(group_options, "strict_range")

            all_params += [
                column_group_key,
                *where_params,
                *directly_linked_aml_partner_params,
                column_group_key,
                *indirectly_linked_aml_partner_params,
                *where_params,
                group_options["date"]["date_from"],
                group_options["date"]["date_to"],
            ]

            # For the move lines directly linked to this partner
            queries.append(
                f"""
                SELECT
                    account_move_line.id,
                    account_move_line.date,
                    account_move_line.date_maturity,
                    account_move_line.name,
                    account_move_line.ref,
                    account_move_line.company_id,
                    account_move_line.account_id,
                    account_move_line.payment_id,
                    account_move_line.partner_id,
                    account_move_line.currency_id,
                    account_move_line.amount_currency,
                    account_move_line.matching_number,
                    {amounts_query},
                    account_move.name                                                                AS move_name,
                    account_move.move_type                                                           AS move_type,
                    account.code                                                                     AS account_code,
                    {account_name}                                                                   AS account_name,
                    journal.code                                                                     AS journal_code,
                    {journal_name}                                                                   AS journal_name,
                    %s                                                                               AS column_group_key,
                    'directly_linked_aml'                                                            AS key,
                    0                                                                                AS partial_id
                FROM {tables}
                JOIN account_move ON account_move.id = account_move_line.move_id
                LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                LEFT JOIN res_company company               ON company.id = account_move_line.company_id
                LEFT JOIN res_partner partner               ON partner.id = account_move_line.partner_id
                LEFT JOIN account_account account           ON account.id = account_move_line.account_id
                LEFT JOIN account_journal journal           ON journal.id = account_move_line.journal_id
                WHERE {where_clause} AND {directly_linked_aml_partner_clause}
                ORDER BY account_move_line.date, account_move_line.id
            """
            )

            # For the move lines linked to no partner, but reconciled with this partner. They will appear in grey in the report
            queries.append(
                f"""
                SELECT
                    account_move_line.id,
                    account_move_line.date,
                    account_move_line.date_maturity,
                    account_move_line.name,
                    account_move_line.ref,
                    account_move_line.company_id,
                    account_move_line.account_id,
                    account_move_line.payment_id,
                    aml_with_partner.partner_id,
                    account_move_line.currency_id,
                    account_move_line.amount_currency,
                    account_move_line.matching_number,
                    CASE WHEN aml_with_partner.balance > 0 THEN 0 ELSE partial.amount END               AS debit,
                    CASE WHEN aml_with_partner.balance < 0 THEN 0 ELSE partial.amount END               AS credit,
                    CASE WHEN aml_with_partner.balance > 0 THEN -partial.amount ELSE partial.amount END AS balance,
                    account_move.name                                                                   AS move_name,
                    account_move.move_type                                                              AS move_type,
                    account.code                                                                        AS account_code,
                    {account_name}                                                                      AS account_name,
                    journal.code                                                                        AS journal_code,
                    {journal_name}                                                                      AS journal_name,
                    %s                                                                                  AS column_group_key,
                    'indirectly_linked_aml'                                                             AS key,
                    partial.id                                                                          AS partial_id
                FROM {tables},
                    account_partial_reconcile partial,
                    account_move,
                    account_move_line aml_with_partner,
                    account_journal journal,
                    account_account account
                WHERE
                    (account_move_line.id = partial.debit_move_id OR account_move_line.id = partial.credit_move_id)
                    AND account_move_line.partner_id IS NULL
                    AND account_move.id = account_move_line.move_id
                    AND (aml_with_partner.id = partial.debit_move_id OR aml_with_partner.id = partial.credit_move_id)
                    AND {indirectly_linked_aml_partner_clause}
                    AND journal.id = account_move_line.journal_id
                    AND account.id = account_move_line.account_id
                    AND {where_clause}
                    AND partial.max_date BETWEEN %s AND %s
                ORDER BY account_move_line.date, account_move_line.id
            """
            )

        query = "(" + ") UNION ALL (".join(queries) + ")"

        if offset:
            query += " OFFSET %s "
            all_params.append(offset)

        if limit:
            query += " LIMIT %s "
            all_params.append(limit)

        self._cr.execute(query, all_params)
        for aml_result in self._cr.dictfetchall():
            if aml_result["key"] == "indirectly_linked_aml":
                # Append the line to the partner found through the reconciliation.
                if aml_result["partner_id"] in rslt:
                    rslt[aml_result["partner_id"]].append(aml_result)

                # Balance it with an additional line in the Unknown Partner section but having reversed amounts.
                if None in rslt:
                    rslt[None].append(
                        {
                            **aml_result,
                            "debit": aml_result["credit"],
                            "credit": aml_result["debit"],
                            "balance": -aml_result["balance"],
                        }
                    )
            else:
                rslt[aml_result["partner_id"]].append(aml_result)

        return rslt
