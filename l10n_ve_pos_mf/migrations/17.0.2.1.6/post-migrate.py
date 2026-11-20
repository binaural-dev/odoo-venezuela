import logging

_logger = logging.getLogger(__name__)


def _fix_report_z_offset(cr):
    """Corrige el desfase de pos_session.report_z (ticket 16520).

    set_report_z siempre guardó ``contador S1 + 1``. Con IoT el S1 se leía
    antes del Z y eso era correcto; con Web Serial se lee DESPUÉS del Z (el
    contador ya es el Z impreso) y la sesión quedó con el número siguiente.

    Corte por caja: solo sesiones posteriores a la última sesión de esa caja
    cuyo report_z coincide con el Z de sus órdenes (época IoT / ya correcta).
    - Con órdenes y report_z = Z órdenes + 1 → Z de las órdenes.
    - Con órdenes y report_z = Z órdenes + 2 → Z de las órdenes. Es un cierre
      reintentado que emitió un segundo Z en cero (Z órdenes + 1).
    - Sin órdenes con Z → report_z - 1.
    Cualquier otro caso no se toca.
    """
    cr.execute(
        """
        WITH order_z AS (
            SELECT session_id, MAX(mf_reportz::int) AS z
              FROM pos_order
             WHERE state != 'cancel'
               AND mf_reportz ~ '^[0-9]+$'
             GROUP BY session_id
        ), cutover AS (
            SELECT s.config_id, MAX(s.start_at) AS start_at
              FROM pos_session s
              JOIN order_z ON order_z.session_id = s.id
             WHERE s.report_z ~ '^[0-9]+$'
               AND s.report_z::int = order_z.z
             GROUP BY s.config_id
        ), fix AS (
            SELECT s.id,
                   s.report_z::int AS old_z,
                   COALESCE(order_z.z, s.report_z::int - 1) AS new_z,
                   (order_z.z IS NOT NULL AND s.report_z::int = order_z.z + 2) AS double_z
              FROM pos_session s
              LEFT JOIN order_z ON order_z.session_id = s.id
              LEFT JOIN cutover ON cutover.config_id = s.config_id
             WHERE s.state = 'closed'
               AND s.report_z ~ '^[0-9]+$'
               AND (cutover.start_at IS NULL OR s.start_at > cutover.start_at)
               AND (order_z.z IS NULL OR s.report_z::int IN (order_z.z + 1, order_z.z + 2))
        )
        UPDATE pos_session s
           SET report_z = fix.new_z::varchar
          FROM fix
         WHERE fix.id = s.id
     RETURNING s.id, s.name, fix.old_z, fix.new_z, fix.double_z
        """
    )
    rows = cr.fetchall()
    _logger.info("l10n_ve_pos_mf: %s sesion(es) con report_z corregido", len(rows))
    for row in rows:
        if row[4]:
            _logger.warning(
                "l10n_ve_pos_mf: sesion %s (%s) cerro con doble Z: report_z %s -> %s; "
                "el Z %s se emitio en cero al reintentar el cierre",
                row[1], row[0], row[2], row[3], row[3] + 1,
            )


def _backfill_serial_machine(cr):
    """serial_machine pasó de related (siempre vacío) a campo guardado.
    Se llena con el serial más usado en las órdenes de cada sesión."""
    cr.execute(
        """
        WITH ranked AS (
            SELECT session_id, fiscal_machine,
                   ROW_NUMBER() OVER (
                       PARTITION BY session_id ORDER BY COUNT(*) DESC, fiscal_machine
                   ) AS rn
              FROM pos_order
             WHERE fiscal_machine IS NOT NULL
               AND fiscal_machine NOT IN ('', 'TFHKA-LOCAL')
             GROUP BY session_id, fiscal_machine
        )
        UPDATE pos_session s
           SET serial_machine = ranked.fiscal_machine
          FROM ranked
         WHERE ranked.session_id = s.id
           AND ranked.rn = 1
           AND COALESCE(s.serial_machine, '') = ''
        """
    )
    _logger.info("l10n_ve_pos_mf: serial_machine llenado en %s sesion(es)", cr.rowcount)


def _mark_z_printed(cr):
    cr.execute(
        """
        UPDATE pos_session
           SET mf_z_printed = TRUE
         WHERE COALESCE(report_z, '') != ''
           AND mf_z_printed IS NOT TRUE
        """
    )


def migrate(cr, version):
    _fix_report_z_offset(cr)
    _backfill_serial_machine(cr)
    _mark_z_printed(cr)
