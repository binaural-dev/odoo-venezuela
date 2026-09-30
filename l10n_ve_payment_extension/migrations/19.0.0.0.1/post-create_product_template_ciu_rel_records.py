"""Pasa el `ciu_id` respaldado por el `pre-` a la tabla del Many2many y suelta la temporal.

Por qué: cierra la conversión Many2one → Many2many que empezó el `pre-` hermano. Solo hace algo
    si ese `pre-` encontró un `ciu_id` que respaldar, o sea en un cliente que venga de una versión
    anterior a la conversión; en uno que viene de 17 no hay columna temporal y esto es no-op.
Si no corre: la columna `temp_ciu_id` queda colgada en `product_template` con los valores viejos
    y **la relación Many2many queda vacía**: los productos pierden su actividad económica (CIU) y
    con ella el cálculo de retención de ISLR, sin ningún error visible.
Revertir: el dato sigue en `temp_ciu_id` hasta que este script la borra; después de eso, se
    reconstruye desde `product_template_ciu_rel`, que es ya el destino definitivo.

El `DELETE` va **acotado a los templates que se están migrando**. La versión original borraba
`product_template_ciu_rel` entera sin filtro, lo que se llevaría por delante cualquier relación
que el módulo o el usuario hubieran creado en productos ajenos a esta conversión.

Tarea: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    if not util.column_exists(cr, "product_template", "temp_ciu_id"):
        _logger.info("no hay temp_ciu_id: el pre- no encontró nada que convertir. Nada que hacer.")
        return

    if not util.table_exists(cr, "product_template_ciu_rel"):
        _logger.warning(
            "temp_ciu_id existe pero la tabla product_template_ciu_rel no: el campo ciu_ids no "
            "llegó a crearse. Se conserva temp_ciu_id para no perder el dato y no se convierte nada."
        )
        return

    cr.execute(
        """
        DELETE FROM product_template_ciu_rel
         WHERE product_template_id IN (
               SELECT id FROM product_template WHERE temp_ciu_id IS NOT NULL
         )
        """
    )
    borradas = cr.rowcount

    cr.execute(
        """
        INSERT INTO product_template_ciu_rel (product_template_id, ciu_id)
        SELECT id, temp_ciu_id FROM product_template WHERE temp_ciu_id IS NOT NULL
        """
    )
    insertadas = cr.rowcount

    cr.execute("ALTER TABLE product_template DROP COLUMN IF EXISTS temp_ciu_id")

    _logger.info(
        "ciu_id -> ciu_ids: %s relaciones creadas (%s reemplazadas)", insertadas, borradas
    )
    if insertadas:
        util.add_to_migration_reports(
            "l10n_ve_payment_extension: la actividad económica (CIU) de los productos pasó de "
            "Many2one a Many2many: %s relaciones creadas." % insertadas,
            category="Binaural · Contabilidad",
        )
