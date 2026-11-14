"""Apply the plan written by ``pre-migrate.py`` (ADR-023).

For every register with several cash payment methods: the first one that is
not in a foreign currency survives as "the cash method" and takes the
currencies of the others in ``currency_ids``; its cross journals by currency
become ``pos.payment.method.currency`` records; the payments of the old
methods move to it with the currency they were made in; the old methods are
archived and leave the register.

Foreign bank methods (Zelle) keep their identity: they only gain the currency
and its cross journals.

A 19 payment of a foreign method knew only its alternate amount
(``foreign_amount``, in the foreign currency of the company). When the method
was in that currency (USD) it is what the customer handed over, so it becomes
``amount_currency``. Odoo 19 valued a method in any other currency (EUR) in the
alternate currency too, so the euros are not recorded anywhere: they are
re-derived from the local amount with the rate of that currency on the day of
the payment. Payments of the method in Bs keep the local amount only, as in
Odoo 19.

The plan table stays for ``l10n_ve_pos_igtf`` (``apply_igtf`` of each merged
method and currency), which drops it.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass('l10n_ve_pos_method_merge')")
    if not cr.fetchone()[0]:
        return
    cr.execute(
        """
        SELECT id, config_id, keeper_id, old_id, currency_id, cross_journal,
               cross_account_journal
          FROM l10n_ve_pos_method_merge
         WHERE NOT done
         ORDER BY id
        """
    )
    plan = cr.fetchall()
    if not plan:
        return
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'account_payment' AND column_name = 'pos_payment_method_id'"
    )
    has_account_payment = bool(cr.fetchone())
    for plan_id, config_id, keeper, old, currency, cross, cross_account in plan:
        merged = keeper != old
        if currency:
            cr.execute(
                """
                INSERT INTO pos_payment_method_res_currency_rel
                    (pos_payment_method_id, res_currency_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
                """,
                (keeper, currency),
            )
            cr.execute(
                """
                INSERT INTO pos_payment_method_currency
                    (payment_method_id, currency_id, company_id, cross_journal,
                     cross_account_journal, create_uid, write_uid, create_date,
                     write_date)
                SELECT %s, %s, m.company_id, %s, %s, 1, 1, now(), now()
                  FROM pos_payment_method m WHERE m.id = %s
                ON CONFLICT (payment_method_id, currency_id) DO UPDATE
                   SET cross_journal = COALESCE(EXCLUDED.cross_journal, pos_payment_method_currency.cross_journal),
                       cross_account_journal = COALESCE(EXCLUDED.cross_account_journal, pos_payment_method_currency.cross_account_journal)
                """,
                (keeper, currency, cross, cross_account, keeper),
            )
            cr.execute(
                """
                SELECT company.foreign_currency_id = %s
                  FROM pos_payment_method method
                  JOIN res_company company ON company.id = method.company_id
                 WHERE method.id = %s
                """,
                (currency, keeper),
            )
            is_alternate = bool((cr.fetchone() or [False])[0])
            cr.execute(
                """
                UPDATE pos_payment payment
                   SET payment_method_id = %(keeper)s,
                       foreign_currency_id = %(currency)s,
                       amount_currency = CASE WHEN %(is_alternate)s
                           THEN payment.foreign_amount
                           ELSE ROUND((payment.amount * COALESCE((
                               SELECT rate.rate
                                 FROM res_currency_rate rate
                                WHERE rate.currency_id = %(currency)s
                                  AND rate.company_id = payment.company_id
                                  AND rate.name <= payment.payment_date::date
                                ORDER BY rate.name DESC
                                LIMIT 1), 0))::numeric, 2)
                       END
                 WHERE payment.payment_method_id = %(old)s
                   AND payment.foreign_currency_id IS NULL
                """,
                {
                    "keeper": keeper,
                    "currency": currency,
                    "old": old,
                    "is_alternate": is_alternate,
                },
            )
        elif merged:
            cr.execute(
                "UPDATE pos_payment SET payment_method_id = %s WHERE payment_method_id = %s",
                (keeper, old),
            )
        if merged:
            if has_account_payment:
                cr.execute(
                    "UPDATE account_payment SET pos_payment_method_id = %s "
                    "WHERE pos_payment_method_id = %s",
                    (keeper, old),
                )
            cr.execute(
                "DELETE FROM pos_config_pos_payment_method_rel "
                "WHERE pos_payment_method_id = %s",
                (old,),
            )
            cr.execute(
                "UPDATE pos_payment_method SET active = FALSE WHERE id = %s", (old,)
            )
        cr.execute(
            "INSERT INTO pos_config_pos_payment_method_rel "
            "(pos_config_id, pos_payment_method_id) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            (config_id, keeper),
        )
        cr.execute("UPDATE l10n_ve_pos_method_merge SET done = TRUE WHERE id = %s", (plan_id,))
    _logger.info("l10n_ve_pos: merged %s cash/foreign payment method entries", len(plan))
