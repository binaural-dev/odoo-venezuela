"""Absorbe el módulo l10n_ve_tax, que no existe en 19, dentro de l10n_ve_accountant.

Qué: borra las vistas de l10n_ve_tax y pasa el resto de lo que el módulo posee (ir.model,
    ir.model.fields, selecciones) a l10n_ve_accountant con util.merge_module, que además borra
    el registro del módulo y sus dependencias. Al terminar la actualización, la limpieza propia
    de Odoo elimina lo que l10n_ve_accountant no declare.

Por qué: los datos de l10n_ve_tax ya los absorbe 19.0.1.0.14 (respalda, renombra y dropea
    columnas), pero el módulo en sí se quedaba en la BD sin código. Tras un -u all:

    - ir_module_module lo deja 'to upgrade' para siempre: "Some modules have inconsistent
      states, some dependencies may be missing: ['l10n_ve_tax']", y migration-verify modulos
      marca el grafo como no sano.
    - Sus 3 vistas siguen activas, y view_account_move_form_binaural_tax usa
      international_purchase_exempt_product, que en 19 se llama international_purchase_exent_product:
      "invalid custom view(s) for model account.move ... El campo
      international_purchase_exempt_product no existe en el modelo account.move.line".

    Hasta ahora la preparación manual lo marcaba 'uninstalled' por SQL antes del -u all, pero eso
    dejaba sus vistas y sus xmlids colgando igual. En Odoo.sh ese paso no existe.

Por qué las vistas se borran antes del merge: si pasaran a l10n_ve_accountant, se aplicarían al
    cargarlo (ir.ui.view._filter_loaded_views) y la de account.move reventaría su carga.

Por qué se marca 'uninstalled' antes del merge: si el módulo absorbido está instalado,
    merge_module llama a force_install_module sobre el destino, y fuera de los scripts de base
    eso dispara el autodescubrimiento de módulos o aborta con MigrationError. l10n_ve_accountant
    ya está instalado, así que no hace falta.

Qué se pierde: nada con datos. Los 10 campos que sólo declaraba l10n_ve_tax ya no tienen columna
    (las dropea el post-migrate de 19.0.1.0.14) y en Proalca estaban vacíos en v17. Los 6 ir.model
    son de modelos que l10n_ve_accountant también extiende: merge_module sólo borra el xmlid
    duplicado.

Qué pasa si no corre: la migración termina, pero con el grafo no sano y una vista rota sobre el
    formulario de facturas.

Cómo revertirlo: no hay nada que revertir. El módulo no tiene código en 19 y sus datos ya estaban
    migrados.

Tarea: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

from odoo.upgrade import util

ABSORBED = "l10n_ve_tax"
INTO = "l10n_ve_accountant"


def migrate(cr, version):
    if not version or not util.module_installed(cr, ABSORBED):
        return

    cr.execute(
        """
        SELECT module || '.' || name
          FROM ir_model_data
         WHERE module = %s
           AND model = 'ir.ui.view'
        """,
        [ABSORBED],
    )
    xml_ids = [xml_id for (xml_id,) in cr.fetchall()]
    if xml_ids:
        util.remove_views(cr, *xml_ids)

    cr.execute("UPDATE ir_module_module SET state = 'uninstalled' WHERE name = %s", [ABSORBED])
    util.merge_module(cr, ABSORBED, INTO)
