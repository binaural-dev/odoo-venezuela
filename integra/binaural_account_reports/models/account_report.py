import re
from odoo import api, fields, models, osv, _
from odoo.tools import get_lang
from odoo.tools.misc import formatLang, format_date
from odoo.exceptions import UserError
from ast import literal_eval
from collections import defaultdict
from ..tools.utils import get_is_foreign_currency

ACCOUNT_CODES_ENGINE_SPLIT_REGEX = re.compile(r"(?=[+-])")

ACCOUNT_CODES_ENGINE_TERM_REGEX = re.compile(
    r"^(?P<sign>[+-]?)"
    r"(?P<prefix>[A-Za-z\d.]*((?=\\)|(?<=[^CD])))"
    r"(\\\((?P<excluded_prefixes>([A-Za-z\d.]+,)*[A-Za-z\d.]*)\))?"
    r"(?P<balance_character>[DC]?)$"
)


class AccountReport(models.Model):
    _inherit = "account.report"

    usd = fields.Boolean(
        string="USD", default=False, help="Check this if the report is gonna be displayed in USD."
    )

    def _create_menu_item_for_report(self):
        """
        Overrides the original method to add the usd_report variable to the context of the action
        that is created for the report, so that we can generate the report in USD if that is the
        case.
        """
        self.ensure_one()

        action = self.env["ir.actions.client"].create(
            {
                "name": self.name,
                "tag": "account_report",
                "context": {"report_id": self.id, "usd_report": self.usd},
            }
        )

        menu_item_vals = {
            "name": self.name,
            "parent_id": self.env["ir.model.data"]._xmlid_to_res_id("account.menu_finance_reports"),
            "action": f"ir.actions.client,{action.id}",
        }

        self.env["ir.ui.menu"].create(menu_item_vals)

    @api.model
    def format_value(self, value, currency=False, blank_if_zero=True, figure_type=None, digits=1):
        """
        Ensure that if the report is in USD, the amount is displayed in its appropiate format.
        Everything else is the same as the original method.
        """
        if figure_type == "none":
            return value

        if value is None:
            return ""

        if figure_type == "monetary":
            # If the report is in USD, we want to display the amount in its appropiate format
            usd_report = True if (self.env.context.get("usd_report") or self.usd) else False
            currency = currency or (
                self.env.ref("base.USD") if usd_report else self.env.ref("base.VEF")
            )
            digits = None
        elif figure_type == "integer":
            currency = None
            digits = 0
        elif figure_type in ("date", "datetime"):
            return format_date(self.env, value)
        else:
            currency = None

        if self.is_zero(value, currency=currency, figure_type=figure_type, digits=digits):
            if blank_if_zero:
                return ""
            # don't print -0.0 in reports
            value = abs(value)

        if self._context.get("no_format"):
            return value

        formatted_amount = formatLang(self.env, value, currency_obj=currency, digits=digits)

        if figure_type == "percentage":
            return f"{formatted_amount}%"

        return formatted_amount

    def export_file(self, options, file_generator):
        """
        Sends the usd_report variable to the request (this way in the controller we can tell if
        the report we are gonna export is in USD or not).
        """
        res = super().export_file(options, file_generator)
        res["data"]["usd_report"] = self.env.context.get("usd_report", False)
        return res

    def _compute_formula_batch_with_engine_tax_tags(
        self,
        options,
        date_scope,
        formulas_dict,
        current_groupby,
        next_groupby,
        offset=0,
        limit=None,
    ):
        """
        Overrides the original method to add the foreign_balance field to the query, so that we
        can get the balance in foreign currency.
        """
        is_foreign_currency = get_is_foreign_currency(self.env)
        if not is_foreign_currency:
            return super()._compute_formula_batch_with_engine_tax_tags(
                options, date_scope, formulas_dict, current_groupby, next_groupby, offset, limit
            )
        self._check_groupby_fields(
            (next_groupby.split(",") if next_groupby else [])
            + ([current_groupby] if current_groupby else [])
        )
        all_expressions = self.env["account.report.expression"]
        for expressions in formulas_dict.values():
            all_expressions |= expressions
        tags = all_expressions._get_matching_tags()

        currency_table_query = self.env["res.currency"]._get_query_currency_table(options)
        groupby_sql = f"account_move_line.{current_groupby}" if current_groupby else None
        tables, where_clause, where_params = self._query_get(options, date_scope)
        tail_query, tail_params = self._get_engine_query_tail(offset, limit)
        if self.pool["account.account.tag"].name.translate:
            lang = self.env.user.lang or get_lang(self.env).code
            acc_tag_name = f"COALESCE(acc_tag.name->>'{lang}', acc_tag.name->>'en_US')"
        else:
            acc_tag_name = "acc_tag.name"
        sql = f"""
            SELECT
                SUBSTRING({acc_tag_name}, 2, LENGTH({acc_tag_name}) - 1) AS formula,
                SUM(ROUND(COALESCE(account_move_line.foreign_balance, 0), currency_table.precision)
                    * CASE WHEN acc_tag.tax_negate THEN -1 ELSE 1 END
                    * CASE WHEN account_move_line.tax_tag_invert THEN -1 ELSE 1 END
                ) AS balance,
                COUNT(account_move_line.id) AS aml_count
                {f', {groupby_sql} AS grouping_key' if groupby_sql else ''}

            FROM {tables}

            JOIN account_account_tag_account_move_line_rel aml_tag
                ON aml_tag.account_move_line_id = account_move_line.id
            JOIN account_account_tag acc_tag
                ON aml_tag.account_account_tag_id = acc_tag.id
                AND acc_tag.id IN %s
            JOIN {currency_table_query}
                ON currency_table.company_id = account_move_line.company_id

            WHERE {where_clause}

            GROUP BY SUBSTRING({acc_tag_name}, 2, LENGTH({acc_tag_name}) - 1)
                {f', {groupby_sql}' if groupby_sql else ''}

            {tail_query}
        """

        params = [tuple(tags.ids)] + where_params + tail_params
        self._cr.execute(sql, params)

        rslt = {
            formula_expr: [] if current_groupby else {"result": 0, "has_sublines": False}
            for formula_expr in formulas_dict.items()
        }
        for query_res in self._cr.dictfetchall():
            formula = query_res["formula"]
            rslt_dict = {"result": query_res["balance"], "has_sublines": query_res["aml_count"] > 0}
            for formula_expr in formulas_dict[formula]:
                if current_groupby:
                    rslt[(formula, formula_expr)].append((query_res["grouping_key"], rslt_dict))
                else:
                    rslt[(formula, formula_expr)] = rslt_dict

        return rslt

    def _compute_formula_batch_with_engine_domain(
        self,
        options,
        date_scope,
        formulas_dict,
        current_groupby,
        next_groupby,
        offset=0,
        limit=None,
    ):
        """
        Overrides the original method to compute the formula in the foreign currency if needed.

        We just change the query to get the foreign_balance instead of the balance, the rest is
        the same as the original method.
        """
        is_foreign_currency = get_is_foreign_currency(self.env)
        if not is_foreign_currency:
            return super()._compute_formula_batch_with_engine_domain(
                options,
                date_scope,
                formulas_dict,
                current_groupby,
                next_groupby,
                offset=offset,
                limit=limit,
            )

        def _format_result_depending_on_groupby(formula_rslt):
            if not current_groupby:
                if formula_rslt:
                    # There should be only one element in the list; we only return its totals (a dict) ; so that a list is only returned in case
                    # of a groupby being unfolded.
                    return formula_rslt[0][1]
                else:
                    # No result at all
                    return {
                        "sum": 0,
                        "sum_if_pos": 0,
                        "sum_if_neg": 0,
                        "count_rows": 0,
                        "has_sublines": False,
                    }
            return formula_rslt

        self._check_groupby_fields(
            (next_groupby.split(",") if next_groupby else [])
            + ([current_groupby] if current_groupby else [])
        )

        groupby_sql = f"account_move_line.{current_groupby}" if current_groupby else None
        ct_query = self.env["res.currency"]._get_query_currency_table(options)

        rslt = {}

        for formula, expressions in formulas_dict.items():
            line_domain = literal_eval(formula)
            tables, where_clause, where_params = self._query_get(
                options, date_scope, domain=line_domain
            )

            tail_query, tail_params = self._get_engine_query_tail(offset, limit)
            # The query is modified to get the foreign_balance instead of the balance.
            query = f"""
                SELECT
                    COALESCE(SUM(ROUND(account_move_line.foreign_balance, currency_table.precision)), 0.0) AS sum,
                    COUNT(DISTINCT account_move_line.{next_groupby.split(',')[0] if next_groupby else 'id'}) AS count_rows
                    {f', {groupby_sql} AS grouping_key' if groupby_sql else ''}
                FROM {tables}
                JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                WHERE {where_clause}
                {f' GROUP BY {groupby_sql}' if groupby_sql else ''}
                {tail_query}
            """

            # Fetch the results.
            formula_rslt = []
            self._cr.execute(query, where_params + tail_params)
            all_query_res = self._cr.dictfetchall()

            total_sum = 0
            for query_res in all_query_res:
                res_sum = query_res["sum"]
                total_sum += res_sum
                totals = {
                    "sum": res_sum,
                    "sum_if_pos": 0,
                    "sum_if_neg": 0,
                    "count_rows": query_res["count_rows"],
                    "has_sublines": query_res["count_rows"] > 0,
                }
                formula_rslt.append((query_res.get("grouping_key", None), totals))

            # Handle sum_if_pos, -sum_if_pos, sum_if_neg and -sum_if_neg
            expressions_by_sign_policy = defaultdict(lambda: self.env["account.report.expression"])
            for expression in expressions:
                subformula_without_sign = expression.subformula.replace("-", "").strip()
                if subformula_without_sign in ("sum_if_pos", "sum_if_neg"):
                    expressions_by_sign_policy[subformula_without_sign] += expression
                else:
                    expressions_by_sign_policy["no_sign_check"] += expression

            # Then we have to check the total of the line and only give results if its sign matches the desired policy.
            # This is important for groupby managements, for which we can't just check the sign query_res by query_res
            if expressions_by_sign_policy["sum_if_pos"] or expressions_by_sign_policy["sum_if_neg"]:
                sign_policy_with_value = (
                    "sum_if_pos"
                    if self.env.company.currency_id.compare_amounts(total_sum, 0.0) >= 0
                    else "sum_if_neg"
                )
                # >= instead of > is intended; usability decision: 0 is considered positive

                formula_rslt_with_sign = [
                    (grouping_key, {**totals, sign_policy_with_value: totals["sum"]})
                    for grouping_key, totals in formula_rslt
                ]

                for sign_policy in ("sum_if_pos", "sum_if_neg"):
                    policy_expressions = expressions_by_sign_policy[sign_policy]

                    if policy_expressions:
                        if sign_policy == sign_policy_with_value:
                            rslt[
                                (formula, policy_expressions)
                            ] = _format_result_depending_on_groupby(formula_rslt_with_sign)
                        else:
                            rslt[
                                (formula, policy_expressions)
                            ] = _format_result_depending_on_groupby([])

            if expressions_by_sign_policy["no_sign_check"]:
                rslt[
                    (formula, expressions_by_sign_policy["no_sign_check"])
                ] = _format_result_depending_on_groupby(formula_rslt)

        return rslt

    def _compute_formula_batch_with_engine_account_codes(
        self,
        options,
        date_scope,
        formulas_dict,
        current_groupby,
        next_groupby,
        offset=0,
        limit=None,
    ):
        """
        Overrides the original method to compute the formulas on the foreign currency if needed.

        We just change the query to get the foreign_balance instead of the balance, the rest is
        the same as the original method.
        """
        is_foreign_currency = get_is_foreign_currency(self.env)
        if not is_foreign_currency:
            return super()._compute_formula_batch_with_engine_account_codes(
                options, date_scope, formulas_dict, current_groupby, next_groupby, offset, limit
            )
        self._check_groupby_fields(
            (next_groupby.split(",") if next_groupby else [])
            + ([current_groupby] if current_groupby else [])
        )

        # Gather the account code prefixes to compute the total from
        prefix_details_by_formula = {}  # in the form {formula: [(1, prefix1), (-1, prefix2)]}
        prefixes_to_compute = set()
        for formula in formulas_dict:
            prefix_details_by_formula[formula] = []
            for token in ACCOUNT_CODES_ENGINE_SPLIT_REGEX.split(formula.replace(" ", "")):
                if token:
                    token_match = ACCOUNT_CODES_ENGINE_TERM_REGEX.match(token)

                    if not token_match:
                        raise UserError(
                            _("Invalid token '%s' in account_codes formula '%s'", token, formula)
                        )

                    parsed_token = token_match.groupdict()

                    if not parsed_token:
                        raise UserError(
                            _("Could not parse account_code formula from token '%s'", token)
                        )

                    multiplicator = -1 if parsed_token["sign"] == "-" else 1
                    excluded_prefixes_match = token_match["excluded_prefixes"]
                    excluded_prefixes = (
                        excluded_prefixes_match.split(",") if excluded_prefixes_match else []
                    )
                    prefix = token_match["prefix"]

                    # We group using both prefix and excluded_prefixes as keys, for the case where two expressions would
                    # include the same prefix, but exlcude different prefixes (example 104\(1041) and 104\(1042))
                    prefix_key = (prefix, *excluded_prefixes)
                    prefix_details_by_formula[formula].append(
                        (multiplicator, prefix_key, token_match["balance_character"])
                    )
                    prefixes_to_compute.add((prefix, tuple(excluded_prefixes)))

        # Create the subquery for the WITH linking our prefixes with account.account entries
        all_prefixes_queries = []
        prefix_params = []
        company_ids = [
            comp_opt["id"] for comp_opt in options.get("multi_company", self.env.company)
        ]
        for prefix, excluded_prefixes in prefixes_to_compute:
            account_domain = [("company_id", "in", company_ids), ("code", "=like", f"{prefix}%")]
            excluded_prefixes_domains = []

            for excluded_prefix in excluded_prefixes:
                excluded_prefixes_domains.append([("code", "=like", f"{excluded_prefix}%")])

            if excluded_prefixes_domains:
                account_domain.append("!")
                account_domain += osv.expression.OR(excluded_prefixes_domains)

            prefix_tables, prefix_where_clause, prefix_where_params = (
                self.env["account.account"]._where_calc(account_domain).get_sql()
            )

            prefix_params.append(prefix)
            for excluded_prefix in excluded_prefixes:
                prefix_params.append(excluded_prefix)

            prefix_select_query = ", ".join(["%s"] * (len(excluded_prefixes) + 1))  # +1 for prefix
            prefix_select_query = f"ARRAY[{prefix_select_query}]"

            all_prefixes_queries.append(
                f"""
                SELECT
                    {prefix_select_query} AS prefix,
                    account_account.id AS account_id
                FROM {prefix_tables}
                WHERE {prefix_where_clause}
            """
            )
            prefix_params += prefix_where_params

        # Build a map to associate each account with the prefixes it matches
        accounts_prefix_map = defaultdict(list)
        self._cr.execute(" UNION ALL ".join(all_prefixes_queries), prefix_params)
        for prefix, account_id in self._cr.fetchall():
            accounts_prefix_map[account_id].append(tuple(prefix))

        # Run main query
        tables, where_clause, where_params = self._query_get(options, date_scope)

        currency_table_query = self.env["res.currency"]._get_query_currency_table(options)
        extra_groupby_sql = f", account_move_line.{current_groupby}" if current_groupby else ""
        extra_select_sql = (
            f", account_move_line.{current_groupby} AS grouping_key" if current_groupby else ""
        )
        tail_query, tail_params = self._get_engine_query_tail(offset, limit)

        query = f"""
            SELECT
                account_move_line.account_id AS account_id,
                SUM(ROUND(account_move_line.foreign_balance, currency_table.precision)) AS sum,
                COUNT(account_move_line.id) AS aml_count
                {extra_select_sql}
            FROM {tables}
            JOIN {currency_table_query} ON currency_table.company_id = account_move_line.company_id
            WHERE {where_clause}
            GROUP BY account_move_line.account_id{extra_groupby_sql}
            {tail_query}
        """
        self._cr.execute(query, where_params + tail_params)

        # Parse result
        rslt = {}

        res_by_prefix_account_id = {}
        for query_res in self._cr.dictfetchall():
            # Done this way so that we can run similar code for groupby and non-groupby
            grouping_key = query_res["grouping_key"] if current_groupby else None
            account_id = query_res["account_id"]
            for prefix_key in accounts_prefix_map[account_id]:
                res_by_prefix_account_id.setdefault(prefix_key, {}).setdefault(
                    account_id, []
                ).append(
                    (
                        grouping_key,
                        {"result": query_res["sum"], "has_sublines": query_res["aml_count"] > 0},
                    )
                )

        for formula, prefix_details in prefix_details_by_formula.items():
            rslt_key = (formula, formulas_dict[formula])
            rslt_destination = rslt.setdefault(
                rslt_key, [] if current_groupby else {"result": 0, "has_sublines": False}
            )
            for multiplicator, prefix_key, balance_character in prefix_details:
                res_by_account_id = res_by_prefix_account_id.get(prefix_key, {})

                for account_results in res_by_account_id.values():
                    account_total_value = sum(
                        group_val["result"] for (group_key, group_val) in account_results
                    )
                    comparator = self.env.company.currency_id.compare_amounts(
                        account_total_value, 0.0
                    )

                    # Manage balance_character.
                    if (
                        not balance_character
                        or (balance_character == "D" and comparator >= 0)
                        or (balance_character == "C" and comparator < 0)
                    ):
                        for group_key, group_val in account_results:
                            rslt_group = {
                                **group_val,
                                "result": multiplicator * group_val["result"],
                            }

                            if current_groupby:
                                rslt_destination.append((group_key, rslt_group))
                            else:
                                rslt_destination["result"] += rslt_group["result"]
                                rslt_destination["has_sublines"] = (
                                    rslt_destination["has_sublines"] or rslt_group["has_sublines"]
                                )

        return rslt


class AccountReportCustomHandler(models.AbstractModel):
    _inherit = "account.report.custom.handler"

    def _get_amount_rows_query(self):
        """
        Computes the string that should go as the rows of the amounts on the queries of the amounts
        from the account move lines. This depends on the action that was used for calling the
        report, as this is the way we know if the user is consulting it on the base or the foreign
        currency.

        Returns
        -------
        string
            The piece of SQL code that goes on the position of the amounts rows for the query.
        """
        report_in_foreign_currency = get_is_foreign_currency(self.env)
        amounts_query = {
            True: """
                ROUND(account_move_line.foreign_debit, currency_table.precision)   AS debit,
                ROUND(account_move_line.foreign_credit, currency_table.precision)  AS credit,
                ROUND(account_move_line.foreign_balance, currency_table.precision) AS balance
            """,
            False: """
                ROUND(account_move_line.debit * currency_table.rate, currency_table.precision)   AS debit,
                ROUND(account_move_line.credit * currency_table.rate, currency_table.precision)  AS credit,
                ROUND(account_move_line.balance * currency_table.rate, currency_table.precision) AS balance
            """,
        }
        return amounts_query[report_in_foreign_currency]

    def _get_sums_amount_rows_query(self):
        """
        Computes the string that should go as the rows of the amounts on the queries of the amounts
        sums from the account move lines. This depends on the action that was used for calling the
        report, as this is the way we know if the user is consulting it on the base or the foreign
        currency.

        Returns
        -------
        string
            The piece of SQL code that goes on the position of the sums of the amounts rows for the
            query.
        """
        report_in_foreign_currency = get_is_foreign_currency(self.env)
        amounts_query = {
            True: """
                COALESCE(SUM(ROUND(account_move_line.foreign_debit, currency_table.precision)), 0.0) AS debit,
                COALESCE(SUM(ROUND(account_move_line.foreign_credit, currency_table.precision)), 0.0) AS credit,
                COALESCE(SUM(ROUND(account_move_line.foreign_balance, currency_table.precision)), 0.0) AS balance
            """,
            False: """
                SUM(ROUND(account_move_line.debit * currency_table.rate, currency_table.precision))   AS debit,
                SUM(ROUND(account_move_line.credit * currency_table.rate, currency_table.precision))  AS credit,
                SUM(ROUND(account_move_line.balance * currency_table.rate, currency_table.precision)) AS balance
            """,
        }
        return amounts_query[report_in_foreign_currency]
