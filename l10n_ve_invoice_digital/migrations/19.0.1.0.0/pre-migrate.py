"""Pre-migration for l10n_ve_invoice_digital: v17 -> v19.

CORRECCIÓN (auditoría posterior, verificada directamente contra el
código actual del módulo): esta versión originalmente asumía que v19
había eliminado por completo el modelo `payment.method.tfhka` y los
campos `account_journal.payment_method_code`, `res_currency.code_tfhka`,
`res_company.dispatch_guide_digital_tfhka` /
`digitalization_with_payment_tfhka`, y respaldaba + eliminaba todo eso.

Esa premisa era FALSA: comparado directamente contra el código actual
de `l10n_ve_invoice_digital` en v19
(models/payment_method_tfhka.py, models/account_journal.py,
models/res_currency.py, models/res_company.py), los 5 son IDÉNTICOS a
v17 -- mismo modelo, misma tabla, mismas columnas, mismo tipo. No hay
nada que respaldar ni migrar: el `post-migrate.py` de esta misma
carpeta hacía `DROP TABLE payment_method_tfhka CASCADE` y `DROP COLUMN`
sobre columnas que el propio módulo v19 sigue declarando y usando --
de haber corrido, habría destruido esquema y datos en vivo (el modelo
Python seguiría declarando el campo, pero la columna física ya no
existiría, causando errores SQL "column/relation does not exist" en
cualquier operación posterior). Se elimina toda esa lógica.

Lo único real de esta carpeta es la brecha semántica documentada
abajo, que sigue siendo válida y no involucra ningún DROP.
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
        "El resto de campos de este módulo (payment.method.tfhka, "
        "account_journal.payment_method_code, res_currency.code_tfhka, "
        "res_company.dispatch_guide_digital_tfhka/"
        "digitalization_with_payment_tfhka) son idénticos entre v17 y v19 -- "
        "no requieren ninguna acción de esta migración."
    )
