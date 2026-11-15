"""Carry the fiscal printer code of the merged payment methods (ADR-023).

``l10n_ve_pos`` merges the cash methods of a register in one that accepts
several currencies and leaves the plan in ``l10n_ve_pos_method_merge``. The
code of the fiscal printer of Odoo 19 hung from each method ("Efectivo Bs.",
"Efectivo $" and "Efectivo EUR" could have a different one, and the printer
treats the codes 20 to 24 as foreign currency): the survivor keeps its own
and takes, per currency, the code of each method it absorbed.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass('l10n_ve_pos_method_merge')")
    if not cr.fetchone()[0]:
        _logger.warning(
            "l10n_ve_pos_mf: no merge plan of l10n_ve_pos, the fiscal printer code of "
            "the merged payment methods is not carried to the currency settings"
        )
        return
    cr.execute(
        """
        UPDATE pos_payment_method_currency setting
           SET code_fiscal_printer = old.code_fiscal_printer
          FROM l10n_ve_pos_method_merge plan
          JOIN pos_payment_method old ON old.id = plan.old_id
         WHERE plan.currency_id IS NOT NULL
           AND plan.keeper_id <> plan.old_id
           AND setting.payment_method_id = plan.keeper_id
           AND setting.currency_id = plan.currency_id
           AND COALESCE(old.code_fiscal_printer, '') <> ''
        """
    )
    _logger.info("l10n_ve_pos_mf: fiscal printer code carried to %s currency settings", cr.rowcount)
