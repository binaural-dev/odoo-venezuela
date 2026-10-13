"""`foreign_balance` quedaba desfasado (p. ej. 25,89) respecto a
`foreign_debit - foreign_credit` (25,90) en lineas reescritas por la
distribucion del residuo alterno. Debito/credito alterno son los valores
que cuadran el asiento: se realinea el saldo con ellos."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE account_move_line
           SET foreign_balance = foreign_debit - foreign_credit
         WHERE foreign_balance IS DISTINCT FROM foreign_debit - foreign_credit
        """
    )
    _logger.info("foreign_balance realigned on %s journal items", cr.rowcount)
