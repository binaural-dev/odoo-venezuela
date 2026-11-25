"""Retira el modo ``auto_post = 'custom'`` en las bases donde este addon ya estuvo instalado
en 19.0.1.0.0 o 19.0.1.0.1.

What: antes de cargar el módulo nuevo,
  1. las cuotas de activo en borrador con ``auto_post = 'custom'`` pasan a ``auto_post =
     'at_date'`` con ``date = auto_post_custom_date`` (su fecha real). También se
     actualiza ``account_move_line.date`` (``related='move_id.date', store=True``), que
     el ORM no propaga en SQL;
  2. las facturas y asientos 'custom' que NO son de activos pasan a ``auto_post = 'no'``
     sin tocar sus fechas, y se deja un warning en el log con sus ids;
  3. cualquier otra fila 'custom' restante pasa a ``auto_post = 'no'``;
  4. se borran las dos vistas que el addon declaraba (``view_move_form_auto_post_custom``
     y ``view_account_asset_form_publish_date``).

Why: al quitar el ``selection_add`` el ``ondelete`` no limpia las filas, y Odoo borra las
columnas ``auto_post_custom_*`` al final del upgrade, así que la fecha real de las cuotas
solo está disponible ahora. Las cuotas conservaban ``date`` = fecha de adquisición mientras
esperaban: sin este paso quedarían en borrador, con fecha de adquisición y sin
publicación automática. Las vistas viejas apuntan a campos que dejan de existir; si siguen
en la base la validación del árbol de ``account.move`` y ``account.asset`` aborta el update
(mismo problema que ``l10n_ve_accountant/migrations/19.0.1.1.1/pre-10-remove_orphan_views``).

Documentos no de activos: el cron del modo custom habría publicado con la fecha contable
nueva y la tasa vieja; no se adivina qué quería el usuario, por eso pasan a 'no' y se
listan para que decida.

If it does not run: cuotas de activo en borrador sin fecha futura y sin publicación
automática, y el update falla al validar las vistas que usan ``auto_post_custom_date``.

Idempotente: si la columna ``auto_post_custom_date`` no existe (base que nunca tuvo la
versión custom) no hace nada.
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

MODULE = "l10n_ve_accountant_asset"
VIEWS = ("view_move_form_auto_post_custom", "view_account_asset_form_publish_date")


def migrate(cr, version):
    if not util.column_exists(cr, "account_move", "auto_post_custom_date"):
        return

    # (1) Cuotas de activo en borrador: su fecha real vuelve a ``date`` y pasan a at_date.
    cr.execute(
        """
        UPDATE account_move
           SET date = auto_post_custom_date,
               auto_post = 'at_date'
         WHERE auto_post = 'custom'
           AND state = 'draft'
           AND asset_id IS NOT NULL
           AND auto_post_custom_date IS NOT NULL
     RETURNING id
        """
    )
    asset_move_ids = [row[0] for row in cr.fetchall()]
    if asset_move_ids:
        cr.execute(
            """
            UPDATE account_move_line line
               SET date = move.date
              FROM account_move move
             WHERE line.move_id = move.id
               AND move.id = ANY(%s)
               AND line.date IS DISTINCT FROM move.date
            """,
            [asset_move_ids],
        )
    _logger.info("%s asset installments moved to auto_post='at_date'", len(asset_move_ids))

    # (2) Facturas y asientos custom que no son de activos: se desactivan y se avisa.
    cr.execute(
        """
        UPDATE account_move
           SET auto_post = 'no'
         WHERE auto_post = 'custom'
           AND asset_id IS NULL
     RETURNING id
        """
    )
    other_ids = [row[0] for row in cr.fetchall()]
    if other_ids:
        _logger.warning(
            "The custom auto-post mode was removed: %s non-asset documents had "
            "auto_post='custom' and now have auto_post='no' (dates untouched). Review them "
            "and schedule them again if needed: %s",
            len(other_ids),
            other_ids,
        )

    # (3) Cualquier otra fila custom restante (p. ej. cuotas sin fecha o ya no en borrador).
    cr.execute("UPDATE account_move SET auto_post = 'no' WHERE auto_post = 'custom' RETURNING id")
    leftover_ids = [row[0] for row in cr.fetchall()]
    if leftover_ids:
        _logger.warning(
            "%s moves still had auto_post='custom' and now have auto_post='no': %s",
            len(leftover_ids),
            leftover_ids,
        )

    # (4) Vistas del modo custom, antes de que el update valide los árboles.
    util.remove_views(cr, *(f"{MODULE}.{name}" for name in VIEWS))
