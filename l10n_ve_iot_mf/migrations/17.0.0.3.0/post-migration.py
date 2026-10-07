import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Corte IoT -> Web Serial en impresión fiscal desde Facturación.

    - Puebla res_company.mf_flag_21 desde el dispositivo fiscal IoT existente
      (si lo hay), para que la impresión Web Serial conserve el formato
      numérico (Flag 21) que ya usaba el cliente.
    - Limpia la vista duplicada de `fiscal_code` en account.tax (ver bloque
      final de este método).
    """
    # 1. Asegurar default en compañías sin valor
    cr.execute("UPDATE res_company SET mf_flag_21 = '00' WHERE mf_flag_21 IS NULL")

    # 2. Si existe un dispositivo fiscal IoT con flag_21 configurado, heredarlo
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables WHERE table_name = 'iot_device'
        )
        """
    )
    if cr.fetchone()[0]:
        cr.execute(
            """
            SELECT flag_21
            FROM iot_device
            WHERE type = 'fiscal_data_module' AND flag_21 IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            """
        )
        row = cr.fetchone()
        if row and row[0]:
            cr.execute("UPDATE res_company SET mf_flag_21 = %s", (row[0],))
            _logger.info(
                "l10n_ve_iot_mf: mf_flag_21 heredado desde iot.device legacy (%s)", row[0]
            )

    # 3. Limpiar vista duplicada de fiscal_code en account.tax.
    #
    # l10n_ve_iot_mf y l10n_ve_pos_mf insertaban ambos el campo `fiscal_code`
    # en la misma posición del formulario de impuestos (account.view_tax_form),
    # causando que el campo apareciera dos veces en la UI cuando ambos módulos
    # estaban instalados. Se eliminó la vista `view_account_tax_form` de
    # l10n_ve_iot_mf (se conserva la de l10n_ve_pos_mf, que tiene un label
    # más descriptivo). Este bloque limpia el registro huérfano que haya
    # quedado en instancias ya migradas a esta misma versión.
    #
    # NOTA: ir_model_data NO tiene FK en cascada hacia ir_ui_view (es una
    # tabla genérica de mapeo XML ID -> cualquier modelo), por lo que hay
    # que eliminar explícitamente ambas filas.
    cr.execute(
        """
        SELECT v.id
        FROM ir_ui_view v
        JOIN ir_model_data d ON d.model = 'ir.ui.view' AND d.res_id = v.id
        WHERE d.module = 'l10n_ve_iot_mf' AND d.name = 'view_account_tax_form'
        """
    )
    row = cr.fetchone()
    if row:
        view_id = row[0]
        cr.execute(
            """
            DELETE FROM ir_model_data
            WHERE model = 'ir.ui.view' AND res_id = %s
              AND module = 'l10n_ve_iot_mf' AND name = 'view_account_tax_form'
            """,
            (view_id,),
        )
        cr.execute("DELETE FROM ir_ui_view WHERE id = %s", (view_id,))
        _logger.info(
            "l10n_ve_iot_mf: eliminada vista duplicada view_account_tax_form (id=%s) - "
            "fiscal_code ya lo provee l10n_ve_pos_mf",
            view_id,
        )
