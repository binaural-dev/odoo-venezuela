import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Corte IoT -> Web Serial en impresión fiscal desde Facturación.

    - Puebla res_company.mf_flag_21 desde el dispositivo fiscal IoT existente
      (si lo hay), para que la impresión Web Serial conserve el formato
      numérico (Flag 21) que ya usaba el cliente.
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
    if not cr.fetchone()[0]:
        return

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
