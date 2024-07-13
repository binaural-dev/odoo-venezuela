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

    def _sub_select(self):
        sub_select_str = """
            SELECT
                (get_members_pending_debt(
                    partner.id,
                    partner.action_number,
                    invoice.fee_period,
                    partner.start_date
                )).*
        """

        return sub_select_str

    def _from(self):
        from_str = """
            FROM
                res_partner partner
        """

        return from_str

    def _join(self):
        join_str = """
            LEFT JOIN LATERAL (
                SELECT fee_period, partner_id FROM account_move 
                WHERE partner_id = partner.id
                AND (payment_state = 'paid' or payment_state = 'in_payment')
                AND account_move.state = 'posted'
                ORDER BY fee_period DESC
                LIMIT 1
            ) invoice ON TRUE
        """

        return join_str

    def _where(self):
        where_str = """
            WHERE partner.action_number IS NOT NULL
            AND partner.state_partner IN ('active', 'holder')
        """

        return where_str


    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE FUNCTION PUBLIC.get_members_pending_debt(p_id BIGINT, act_number BIGINT, invoice_fee_period DATE, start_date DATE)
                RETURNS TABLE(partner_id BIGINT, action_number BIGINT, quota_period DATE, amount FLOAT) AS $$
                DECLARE 
                    _effective_date DATE;
                    _tmp_next_date DATE;
                    _day_end_date_payment INTEGER;
                    _is_postpaid BOOLEAN;
                BEGIN
                    SELECT day_end_date_payment INTO _day_end_date_payment FROM partner_config LIMIT 1;
                    SELECT is_postpaid INTO _is_postpaid FROM partner_config LIMIT 1;

                    IF invoice_fee_period IS NULL THEN
                        _effective_date := start_date;
                    ELSE
                        _effective_date := invoice_fee_period;
                    END IF;

                    _effective_date := date_trunc('month', _effective_date);

                    IF _is_postpaid THEN
                        _effective_date := (date_trunc('month', _effective_date) + INTERVAL '1 month');
                    END IF;

                    IF _effective_date <= CURRENT_DATE AND EXTRACT(DAY FROM CURRENT_DATE) >= _day_end_date_payment THEN
                        _tmp_next_date := _effective_date;
                    ELSE
                        IF EXTRACT(DAY FROM CURRENT_DATE) < _day_end_date_payment THEN
                            _tmp_next_date := date_trunc('month', _effective_date) + INTERVAL '1 month';
                        ELSE
                            _tmp_next_date := date_trunc('month', _effective_date);
                        END IF;
                    END IF;

                    WHILE _tmp_next_date <= (date_trunc('month', NOW()) + INTERVAL '1 month')::DATE + (_day_end_date_payment -1) LOOP
                        RAISE NOTICE 'Processing date: %', _tmp_next_date;

                        IF invoice_fee_period IS NOT NULL AND EXTRACT(DAY FROM invoice_fee_period) > _day_end_date_payment THEN
                            IF EXTRACT(MONTH FROM _tmp_next_date) = EXTRACT(MONTH FROM invoice_fee_period) 
                            AND EXTRACT(YEAR FROM _tmp_next_date) = EXTRACT(YEAR FROM invoice_fee_period) THEN
                                _tmp_next_date := _tmp_next_date + INTERVAL '1 month';
                                CONTINUE;
                            END IF;
                        END IF;

                        IF EXTRACT(DAY FROM CURRENT_DATE) < _day_end_date_payment THEN
                            IF EXTRACT(MONTH FROM _tmp_next_date) = EXTRACT(MONTH FROM NOW()) 
                            AND EXTRACT(YEAR FROM _tmp_next_date) = EXTRACT(YEAR FROM NOW()) THEN
                                EXIT;
                            END IF;
                        END IF;

                        RETURN QUERY
                        SELECT 
                            p_id AS partner_id,
                            act_number AS action_number,
                            _tmp_next_date AS quota_period,
                            (SELECT pdl.amount FROM pending_debt_list pdl 
                            WHERE pdl.date_end >= _tmp_next_date OR pdl.date_end IS NULL 
                            ORDER BY pdl.date_end ASC LIMIT 1) AS amount;

                        _tmp_next_date := _tmp_next_date + INTERVAL '1 month';
                    END LOOP;
                END;

                $$ LANGUAGE plpgsql;
            """
        )
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %s AS (
                %s
                FROM (
                    %s
                    %s
                    %s
                    %s
                ) debts
            );
            """
            % (
                self._table,
                self._select(),
                self._sub_select(),
                self._from(),
                self._join(),
                self._where(),
            )
        )
