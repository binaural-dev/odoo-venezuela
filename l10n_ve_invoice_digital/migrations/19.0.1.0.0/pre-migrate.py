"""Pre-migration for l10n_ve_invoice_digital: v17 -> v19.

CORRECTION (later audit, verified directly against the current code of
the module): this version originally assumed that v19 had completely
removed the `payment.method.tfhka` model and the fields
`account_journal.payment_method_code`, `res_currency.code_tfhka`,
`res_company.dispatch_guide_digital_tfhka` /
`digitalization_with_payment_tfhka`, and backed up + deleted all of that.

That premise was FALSE: compared directly against the current code
of `l10n_ve_invoice_digital` in v19
(models/payment_method_tfhka.py, models/account_journal.py,
models/res_currency.py, models/res_company.py), all 5 are IDENTICAL to
v17 -- same model, same table, same columns, same type. There is
nothing to back up or migrate: the `post-migrate.py` in this same
folder ran `DROP TABLE payment_method_tfhka CASCADE` and `DROP COLUMN`
on columns that the v19 module itself still declares and uses --
had it run, it would have destroyed live schema and data (the Python
model would still declare the field, but the physical column would no
longer exist, causing SQL errors "column/relation does not exist" in
any later operation). All of that logic is removed.

The only real thing in this folder is the semantic gap documented
below, which is still valid and does not involve any DROP.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.warning(
        "l10n_ve_invoice_digital pre-migrate: v19 tracks digitization per "
        "stock.picking (is_digitalized/control_number_tfhka), a concept that "
        "did not exist in v17 (only company-wide flags did). Historical "
        "pickings will come out of this migration with is_digitalized=False "
        "regardless of whether they were actually sent to TFHKA under the "
        "old flow -- there is no v17 data to derive that from per-picking. "
        "The rest of the fields of this module (payment.method.tfhka, "
        "account_journal.payment_method_code, res_currency.code_tfhka, "
        "res_company.dispatch_guide_digital_tfhka/"
        "digitalization_with_payment_tfhka) are identical between v17 and v19 -- "
        "they do not require any action from this migration."
    )
