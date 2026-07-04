import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Limpieza de vista duplicada de fiscal_code en account.tax.

    l10n_ve_iot_mf y l10n_ve_pos_mf insertaban ambos el campo `fiscal_code`
    en la misma posición del formulario de impuestos (account.view_tax_form),
    causando que el campo apareciera dos veces en la UI cuando ambos módulos
    estaban instalados. Se eliminó la vista `view_account_tax_form` de
    l10n_ve_iot_mf (se conserva la de l10n_ve_pos_mf, que tiene un label
    más descriptivo). Esta migración limpia el registro huérfano que haya
    quedado en instancias ya migradas.
    """
    cr.execute(
        """
        SELECT v.id
        FROM ir_ui_view v
        JOIN ir_model_data d ON d.model = 'ir.ui.view' AND d.res_id = v.id
        WHERE d.module = 'l10n_ve_iot_mf' AND d.name = 'view_account_tax_form'
        """
    )
    row = cr.fetchone()
    if not row:
        return

    view_id = row[0]
    cr.execute("DELETE FROM ir_model_data WHERE model = 'ir.ui.view' AND res_id = %s AND module = 'l10n_ve_iot_mf' AND name = 'view_account_tax_form'", (view_id,))
    cr.execute("DELETE FROM ir_ui_view WHERE id = %s", (view_id,))
    _logger.info(
        "l10n_ve_iot_mf: eliminada vista duplicada view_account_tax_form (id=%s) - fiscal_code ya lo provee l10n_ve_pos_mf",
        view_id,
    )
