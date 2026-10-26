"""Post-migration for l10n_ve_invoice_digital 19.0.1.0.0.

See pre-migrate.py in this same folder: all the DROP COLUMN/DROP TABLE
that this file did on payment.method.tfhka,
account_journal.payment_method_code, res_currency.code_tfhka,
res_company.dispatch_guide_digital_tfhka and
digitalization_with_payment_tfhka was removed -- verified that all 5
are identical between v17 and current v19, they were never orphans.
This version has no post-migrate action to run.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(
        "l10n_ve_invoice_digital post-migrate (19.0.1.0.0): no actions -- "
        "see pre-migrate.py, the TFHKA schema is identical between v17 and v19"
    )
