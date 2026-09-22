"""Retira los módulos de anticipos que l10n_ve_igtf absorbe, todos juntos y cuando ya no hay vuelta atrás.

Qué: marca 'to remove' a los módulos de MODULES_TO_RETIRE que estén instalados y a todos los que
    dependan de ellos, directa o indirectamente. El paso 5 de la carga de Odoo, que corre justo
    después de los end-, los desinstala.

Por qué: el pre-migrate de 19.0.1.2.16 ya los marca, pero en un pre- eso no funciona. El grafo de
    módulos ya está armado y Odoo carga igual los que vienen después de l10n_ve_igtf; al
    cargarlos los devuelve a 'installed' y la marca se pierde. Sólo se retiran los que Odoo cargó
    antes de l10n_ve_igtf. La simulación del flujo de Odoo.sh sobre Proalca, sin preparación
    manual, terminó así:

      binaural_advance_payment             uninstalled
      binaural_advance_payment_igtf        installed  -> depende de binaural_advance_payment
      binaural_subsidiary_payment_advance  installed  -> depende de binaural_advance_payment

      ERROR Some modules are not loaded, some dependencies or manifest may be missing:
            ['binaural_advance_payment_igtf', 'binaural_subsidiary_payment_advance',
             'binaural_subsidiary_payment_advance_igtf']

    Un retiro a medias es peor que ninguno: los que quedan instalados no pueden volver a
    cargarse nunca.

Por qué en un end-: los end- corren cuando ya se cargó todo (paso 3.5 de
    odoo/modules/loading.py) y antes de que Odoo desinstale lo marcado (paso 5). Lo que se marca
    aquí no lo puede desmarcar nadie. Es lo mismo que hacía a mano el paso 3 de la preparación
    (08-procedimiento-upgrade-bd.md) y que dejó la corrida de referencia run14 con 8 de 8 puntos
    contables exactos; la diferencia es que ahora corre también en Odoo.sh, donde ese paso no
    existe.

Por qué también los dependientes: el paso 5 desinstala exactamente lo marcado. Sin marcar la
    cadena entera, un puente como binaural_subsidiary_payment_advance_igtf (auto_install) quedaría
    instalado colgando de un módulo desinstalado. Si en la cadena aparece un módulo que no es de
    la familia de anticipos, se retira igual —dejarlo sería peor—, pero se avisa en el log y en
    el reporte de migración, porque eso sí hay que mirarlo.

Qué se pierde: lo que la desinstalación borra de estos módulos. Sus campos que l10n_ve_igtf no
    declara ya los respalda y los dropea 19.0.1.2.16 (l10n_ve_igtf_migration_v17_backup). Lo que
    l10n_ve_igtf sí declara no se toca: Odoo no borra un registro que otro módulo instalado
    también posee.

Qué pasa si no corre: quedan instalados con su dependencia desinstalada, y migration-verify
    modulos marca el grafo como no sano.

Cómo revertirlo: volver a instalar los módulos. Sus datos exclusivos se recuperan desde la tabla
    de respaldo.

Tarea: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# La misma lista que el pre-migrate de 19.0.1.2.16.
MODULES_TO_RETIRE = [
    "binaural_advance_payment_igtf",
    "binaural_advance_payment",
    "binaural_advance_payment_report",
    "binaural_subsidiary_payment_advance",
]

# Dependientes que se sabe que salen con ellos: puentes auto_install de la misma familia.
KNOWN_DEPENDANTS = {"binaural_subsidiary_payment_advance_igtf"}

INSTALLED_STATES = ("installed", "to upgrade", "to install", "to remove")


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        WITH RECURSIVE retiro(name) AS (
            SELECT unnest(%s::varchar[])
             UNION
            SELECT m.name
              FROM ir_module_module m
              JOIN ir_module_module_dependency d ON d.module_id = m.id
              JOIN retiro r ON d.name = r.name
        )
        SELECT m.name
          FROM ir_module_module m
          JOIN retiro r ON r.name = m.name
         WHERE m.state IN %s
        """,
        [MODULES_TO_RETIRE, INSTALLED_STATES],
    )
    names = sorted(name for (name,) in cr.fetchall())
    if not names:
        return

    cr.execute("UPDATE ir_module_module SET state = 'to remove' WHERE name IN %s", [tuple(names)])
    _logger.info("Marcados para desinstalar al final de la actualización: %s", ", ".join(names))

    unexpected = sorted(set(names) - set(MODULES_TO_RETIRE) - KNOWN_DEPENDANTS)
    if unexpected:
        msg = (
            "Se desinstalan porque dependen de los módulos de anticipos que absorbe l10n_ve_igtf: "
            "{}. Revisar que no fueran necesarios.".format(", ".join(unexpected))
        )
        _logger.warning(msg)
        util.add_to_migration_reports(msg, category="Binaural · l10n_ve_igtf")
