"""Carry the IGTF flag of the payment methods over to the currency settings (ADR-023).

In Odoo 19 ``apply_igtf`` was a flag of the payment method, and each foreign
currency had its own method ("Efectivo $", "Efectivo EUR", Zelle). In Odoo 20
the method takes several currencies and the flag lives in
``pos.payment.method.currency``, one setting per method and currency.

``l10n_ve_pos`` (its ``pre-migrate.py``) leaves the plan of the merge in
``l10n_ve_pos_method_merge`` with the ``apply_igtf`` each old method had, and
``post-migrate.py`` applies it; this step reads it to set the flag on the
setting of the method that survives. It does not drop the table: the other
modules read it too, and the ``end-migrate.py`` of ``l10n_ve_pos`` drops it.

A method in the currency of the register (Bs) that had the flag has no setting
to hold it: IGTF is charged on payments in foreign currency. They are listed in
the log so the accountant decides.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass('l10n_ve_pos_method_merge')")
    if not cr.fetchone()[0]:
        return
    cr.execute("SELECT COUNT(*) FROM l10n_ve_pos_method_merge WHERE NOT done")
    if cr.fetchone()[0]:
        _logger.warning(
            "l10n_ve_pos_igtf: the merge of the payment methods of l10n_ve_pos is not "
            "applied, the table l10n_ve_pos_method_merge is kept"
        )
        return
    cr.execute(
        """
        UPDATE pos_payment_method_currency setting
           SET apply_igtf = TRUE
          FROM (
                SELECT keeper_id, currency_id
                  FROM l10n_ve_pos_method_merge
                 WHERE currency_id IS NOT NULL
                 GROUP BY keeper_id, currency_id
                HAVING BOOL_OR(apply_igtf)
               ) plan
         WHERE setting.payment_method_id = plan.keeper_id
           AND setting.currency_id = plan.currency_id
        """
    )
    _logger.info("l10n_ve_pos_igtf: apply_igtf set on %s currency settings", cr.rowcount)
    cr.execute(
        """
        SELECT DISTINCT old_id
          FROM l10n_ve_pos_method_merge
         WHERE currency_id IS NULL AND apply_igtf
        """
    )
    lost = [row[0] for row in cr.fetchall()]
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'pos_payment_method' AND column_name = 'apply_igtf'"
    )
    if cr.fetchone():
        cr.execute(
            """
            SELECT method.id
              FROM pos_payment_method method
             WHERE method.apply_igtf
               AND NOT EXISTS (
                   SELECT 1 FROM l10n_ve_pos_method_merge plan
                    WHERE plan.old_id = method.id AND plan.currency_id IS NOT NULL
               )
            """
        )
        lost = sorted(set(lost) | {row[0] for row in cr.fetchall()})
    if lost:
        _logger.warning(
            "l10n_ve_pos_igtf: the payment methods %s had IGTF but take payments in the "
            "currency of the register: IGTF is charged on foreign currency payments and "
            "is not applied to them in Odoo 20",
            lost,
        )
