"""Post-migration for l10n_ve_igtf 19.0.1.2.17.

Nada que hacer aquí: 19.0.1.2.16/post-migrate.py ya dropea
EXCLUSIVE_COLUMNS (mismas columnas, sin cambios en esta versión) y esa
versión corre siempre antes que esta en el mismo -u. El único cambio de
19.0.1.2.17 es el rename de pre-migrate.py (RENAMED_COLUMNS), que no
necesita ningún paso de post-migrate.

(Ver el docstring de pre-migrate.py en esta misma carpeta: la sección
de retiro de binaural_igtf/binaural_base_igtf para la línea no
homologada que originalmente vivía aquí se movió a
l10n_ve_igtf/__init__.py -- pre_init_hook -- porque este archivo nunca
se ejecuta en instalación nueva de módulo.)
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("l10n_ve_igtf post-migrate (19.0.1.2.17): sin acciones adicionales")
