"""Rellena payment_account_id en lineas de metodo de pago de diarios banco
existentes desde default_account_id del diario.

Sin esto, diarios banco creados antes de este cambio (cuyas lineas nunca
pasaron por el fill de account_journal.py ni por el create() nuevo de
account_payment_method_line.py) quedarian bloqueados para confirmar pagos
en cuanto se actualice el modulo (constrains nuevo + guard de action_post,
PR #1344 / task 81735).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE account_payment_method_line AS apml
        SET payment_account_id = aj.default_account_id
        FROM account_journal AS aj
        WHERE apml.journal_id = aj.id
          AND aj.type = 'bank'
          AND apml.payment_account_id IS NULL
          AND aj.default_account_id IS NOT NULL
        """
    )

    cr.execute(
        """
        SELECT DISTINCT aj.id, aj.name
        FROM account_journal AS aj
        JOIN account_payment_method_line AS apml ON apml.journal_id = aj.id
        WHERE aj.type = 'bank'
          AND apml.payment_account_id IS NULL
          AND aj.default_account_id IS NULL
        """
    )
    unresolved = cr.fetchall()
    if unresolved:
        _logger.warning(
            "l10n_ve_accountant: %d diario(s) banco sin default_account_id, sus "
            "lineas de metodo de pago quedan sin cuenta tras esta migracion "
            "(bloquearan la confirmacion de pagos hasta configurarse): %s",
            len(unresolved),
            ", ".join(f"{jid} ({name})" for jid, name in unresolved),
        )
