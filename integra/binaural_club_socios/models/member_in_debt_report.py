from odoo import _, api, fields, models
from odoo import tools
import logging

_logger = logging.getLogger(__name__)

class MemberInDebtReport(models.Model):
    _name = "member.in.debt.report"
    _description = "Report for member in debt based in a close date"
    _auto = False

    partner_id = fields.Many2one("res.partner", string="Socio")
    action_number = fields.Many2one("action.partner", string="Número de Acción")
    quota_period = fields.Date("Periodo de Cuota")
    quota_period_str = fields.Char("Periodo de la Cuota", compute="_compute_quota_period_str")
    amount = fields.Float("Monto")

    @api.depends("quota_period")
    def _compute_quota_period_str(self):
        for debt_member in self:
            debt_member.quota_period_str = debt_member.quota_period.strftime("%m/%Y")

    # Builders Main Select
    def _select(self):
        select_str = """
            SELECT
                row_number() OVER () AS id,
                debts.partner_id,
                debts.action_number,
                debts.quota_period,
                debts.amount
        """

        return select_str

    def _from(self):
        from_str = """
            FROM
                get_members_pending_debts()
        """

        return from_str

    def _where(self):
        where_str = """
            WHERE debts.amount > 0
        """

        return where_str

    # Builder From Sub Query
    def _from_sub_select(self):
        sub_select_str = """
            SELECT
                (get_members_pending_debt(
                    partner.id,
                    partner.action_number,
                    partner.start_date
                )).*
        """

        return sub_select_str
    
    def _from_sub_select_from(self):
        from_str = """
            FROM
                res_partner partner
        """

        return from_str
    
    def _from_sub_select_join(self):
        join_str = """
            LEFT JOIN LATERAL (
                SELECT 
				account_move.fee_period,
				account_move.partner_id
                FROM account_move 
                WHERE 
                    account_move.partner_id = partner.id
                    AND (
                            account_move.payment_state = 'paid' or account_move.payment_state = 'in_payment'
                        )
                    AND account_move.state = 'posted'
                ORDER BY account_move.fee_period DESC
                LIMIT 1
            ) invoice ON TRUE
        """

        return join_str
    
    def _from_sub_select_where(self):
        where_str = """
            WHERE partner.action_number IS NOT NULL
            AND partner.state_partner IN ('active', 'holder');
        """

        return where_str

    # Declaring Functions
    def _sql_function_get_members_pending_debt(self):
        sql_function_get_members_pending_debt = """
            CREATE OR REPLACE FUNCTION PUBLIC.get_members_pending_debt(p_id BIGINT, act_number BIGINT, start_date DATE)
                RETURNS TABLE(partner_id BIGINT, action_number BIGINT, quota_period DATE, amount FLOAT) AS $$
                DECLARE
                    _effective_date DATE;
                    _tmp_next_date DATE;
                    _invoice_paid_for_fee_period DATE;
                    _day_end_date_payment INTEGER;
                    _is_postpaid BOOLEAN;
                    _max_fee_period_amount double precision;
                    _current_amount double precision;
                    _amount double precision;
                BEGIN
                    SELECT day_end_date_payment INTO _day_end_date_payment FROM partner_config LIMIT 1;
                    SELECT is_postpaid INTO _is_postpaid FROM partner_config LIMIT 1;

                    -- Obtener el monto de cuota mas reciente
                    SELECT 
                        pdl.amount
                    INTO _max_fee_period_amount
                    FROM pending_debt_list pdl 
                    WHERE 
                        pdl.date_end IS NOT NULL 
                    ORDER BY pdl.date_end DESC 
                    LIMIT 1;

                    -- 	Obtener la fecha de periodo de cuota mas reciente
                    SELECT 
                        account_move.fee_period
                    INTO 
                        _invoice_paid_for_fee_period
                    FROM account_move
                    WHERE
                        account_move.partner_id = p_id
                        AND account_move.state = 'posted'
                        AND account_move.fee_period IS NOT NULL
                        AND (
                            account_move.payment_state = 'paid'
                            OR account_move.payment_state = 'in_payment'
                        )
                    ORDER BY account_move.fee_period DESC
                    LIMIT 1;

                    IF _invoice_paid_for_fee_period IS NULL THEN
                        _effective_date := start_date;

                        -- 		IF _is_postpaid THEN
                        -- 			_effective_date := (date_trunc('month', _effective_date) + INTERVAL '1 month');
                        --      END IF;

                    ELSE
                        _effective_date := _invoice_paid_for_fee_period;
                    END IF;

                    _effective_date := date_trunc('month', _effective_date);

                    _tmp_next_date := _effective_date;

                -- 	IF _effective_date <= CURRENT_DATE AND EXTRACT(DAY FROM CURRENT_DATE) >= _day_end_date_payment THEN
                -- 		_tmp_next_date := _effective_date;
                -- 	ELSE
                -- 		IF EXTRACT(DAY FROM CURRENT_DATE) < _day_end_date_payment THEN
                -- 			_tmp_next_date := date_trunc('month', _effective_date) + INTERVAL '1 month';
                -- 		ELSE
                -- 			_tmp_next_date := date_trunc('month', _effective_date);
                -- 		END IF;
                -- 	END IF;

                    WHILE _tmp_next_date <= (date_trunc('month', NOW()) + INTERVAL '1 month')::DATE + (_day_end_date_payment -1) LOOP
                        RAISE NOTICE 'Processing date: %', _tmp_next_date;

                        IF EXTRACT(DAY FROM CURRENT_DATE) < _day_end_date_payment THEN
                            IF EXTRACT(MONTH FROM _tmp_next_date) = EXTRACT(MONTH FROM NOW()) 
                            AND EXTRACT(YEAR FROM _tmp_next_date) = EXTRACT(YEAR FROM NOW()) THEN
                                EXIT;
                            END IF;
                        END IF;

                        SELECT 
                            pdl.amount
                        INTO _current_amount
                        FROM pending_debt_list pdl 
                        WHERE 
                            pdl.date_end >= _tmp_next_date 
                            OR pdl.date_end IS NULL 
                        ORDER BY pdl.date_end ASC 
                        LIMIT 1;

                        IF _current_amount IS NOT NULL THEN
                            _amount := _current_amount;
                        END IF;

                        IF _amount IS NULL THEN
                            _amount := _max_fee_period_amount;
                        END IF;

                        RETURN QUERY
                        SELECT 
                            p_id AS partner_id,
                            act_number AS action_number,
                            _tmp_next_date AS quota_period,
                            _amount AS amount;

                        _tmp_next_date := _tmp_next_date + INTERVAL '1 month';
                    END LOOP;
                END;


                $$ LANGUAGE plpgsql;
        """

        return sql_function_get_members_pending_debt

    def _sql_function_get_members_pending_debts(self):
        sql_function_get_members_pending_debts = ("""
            CREATE OR REPLACE FUNCTION PUBLIC.get_members_pending_debts()
                RETURNS TABLE(partner_id BIGINT, action_number BIGINT, quota_period DATE, amount FLOAT) AS $$
                DECLARE 

                BEGIN

                RETURN QUERY
                    %s
                    %s
                    %s
                    %s
                END;

                $$ LANGUAGE plpgsql;
        """
        % (
            self._from_sub_select(),
            self._from_sub_select_from(),
            self._from_sub_select_join(),
            self._from_sub_select_where()
        ))

        return sql_function_get_members_pending_debts

    def _sql_view(self):
        return (
            """
                CREATE OR REPLACE VIEW %s AS (
                    %s
                    FROM get_members_pending_debts() debts
                    %s
                );
            """
            % (
                self._table,
                self._select(),
                self._where()
            )
        )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        
        sql_function_get_members_pending_debt = self._sql_function_get_members_pending_debt()
        sql_function_get_members_pending_debts = self._sql_function_get_members_pending_debts()
        
        sql_view = self._sql_view()

        self.env.cr.execute(
            sql_function_get_members_pending_debt
        )

        self.env.cr.execute(
            sql_function_get_members_pending_debts
        )

        self.env.cr.execute(
            sql_view
        )
