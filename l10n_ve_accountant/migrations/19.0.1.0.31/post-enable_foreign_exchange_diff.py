"""`l10n_ve_use_foreign_exchange_diff` pasa a ser True por defecto: se activa
en las companias existentes que ya tienen configurados el diario y las cuentas
de ganancia/perdida cambiaria (requeridos por su constraint). Las que no los
tienen se dejan como estan para no romper su configuracion."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE res_company
           SET l10n_ve_use_foreign_exchange_diff = TRUE
         WHERE l10n_ve_use_foreign_exchange_diff IS NOT TRUE
           AND currency_exchange_journal_id IS NOT NULL
           AND income_currency_exchange_account_id IS NOT NULL
           AND expense_currency_exchange_account_id IS NOT NULL
        """
    )
    _logger.info("l10n_ve_use_foreign_exchange_diff enabled on %s companies", cr.rowcount)
