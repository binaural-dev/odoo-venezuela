"""Borra las vistas que l10n_ve_currency_rate_live declaraba en 17 y en 19 ya no.

Qué: elimina estas vistas junto con las que heredan de ellas, por SQL y con
util.remove_views. Las heredadas que son de un módulo se borran; las que
creó un usuario se desactivan y quedan en el reporte de migración.

Por qué: una vista que el módulo dejó de declarar no la reescribe nadie, y
se queda en la BD tal como vino de 17. Si su xpath se ancla a algo que en 19
ya no existe, en cuanto se carga una vista hermana Odoo revalida el árbol de
su modelo, no encuentra el ancla y el ParseError aborta la migración entera.
La limpieza propia de Odoo, la de los registros cuyo xmlid desapareció,
corre al final de todo el -u: demasiado tarde.

Qué pasa si no corre: el -u all muere al cargar este módulo con "El elemento
<xpath ...> no se puede localizar en la vista principal". Así murió la
simulación del flujo de Odoo.sh sobre Proalca, sin la limpieza manual previa
que hacía `migration-verify vistas --borrar`.

Por qué alcanza con un pre- de este mismo módulo: durante una actualización,
Odoo sólo aplica las vistas de los módulos ya cargados y del que se está
cargando (ir.ui.view._filter_loaded_views). Las vistas de este módulo no
cuentan hasta que se carga, y este script corre justo antes.

Por qué por SQL y no por el ORM: en un pre- el modelo todavía no terminó de
armarse, y un unlink() sobre ir.ui.view dispara la validación del árbol
contra un modelo incompleto.

De dónde sale la lista: del código, no de una BD. Son las vistas que las
ramas 17 (17.0 y l10nve_17.0) declaran y 19 ya no. Sirve igual para
cualquier cliente que venga de 17; las que no estén en su BD se ignoran.

Cómo revertirlo: no hace falta. Si una vista estuviera aquí por error, la
carga del módulo la vuelve a crear desde su archivo de datos.

Tarea: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

from odoo.upgrade import util

MODULE = "l10n_ve_currency_rate_live"

ORPHAN_VIEWS = [
    "res_config_settings_view_form_inherit_rates",
]


def migrate(cr, version):
    util.remove_views(cr, *(f"{MODULE}.{name}" for name in ORPHAN_VIEWS))
