"""Post-migration for l10n_ve_invoice_digital 19.0.1.0.0.

Ver pre-migrate.py en esta misma carpeta: se eliminó todo el
DROP COLUMN/DROP TABLE que este archivo hacía sobre
payment.method.tfhka, account_journal.payment_method_code,
res_currency.code_tfhka, res_company.dispatch_guide_digital_tfhka y
digitalization_with_payment_tfhka -- verificado que los 5 son
idénticos entre v17 y v19 actual, nunca fueron huérfanos. Esta versión
no tiene ninguna acción de post-migrate que ejecutar.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(
        "l10n_ve_invoice_digital post-migrate (19.0.1.0.0): sin acciones -- "
        "ver pre-migrate.py, el esquema TFHKA es idéntico entre v17 y v19"
    )
