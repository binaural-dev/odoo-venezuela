"""Da group_foreign_currency_view_accountant a los usuarios internos que vienen de 17.

Qué: agrega al grupo a todos los usuarios internos (share = False), activos y archivados.

Por qué: el grupo es nuevo en 19 (6933e4079) y protege la pestaña "Foreign currency" de la
    factura, con los totales en moneda alterna (views/account_move.xml). En 17 esa pestaña no
    tenía grupo: la veía cualquiera que abriera una factura. El grupo no se siembra en ningún
    usuario, ni siquiera en base.user_admin, así que después del -u all nadie la ve. En la
    sesión 13 así quedó proalca19_db, con 0 usuarios en el grupo.

    Se da a todos los internos y no sólo a contabilidad para que la migración no cambie lo que
    cada usuario veía en 17. Quién lo debe tener de ahí en adelante es una decisión del cliente,
    que se toma desde Ajustes → Usuarios.

Qué pasa si no corre: en todas las facturas migradas desaparece para todos la pestaña con los
    totales en $.

Cómo revertirlo: sacar a los usuarios del grupo desde Ajustes. No toca ningún otro dato.

Tarea: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return

    env = util.env(cr)
    group = env.ref("l10n_ve_accountant.group_foreign_currency_view_accountant", raise_if_not_found=False)
    if not group:
        return
    users = env["res.users"].with_context(active_test=False).search([("share", "=", False)]) - group.user_ids
    if users:
        group.write({"user_ids": [(4, user.id) for user in users]})
    _logger.info("%s usuarios internos agregados a %s", len(users), group.name)
