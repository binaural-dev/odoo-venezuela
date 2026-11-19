"""Post-migración de l10n_ve_pos_mf 19.0.3.2.1 (ticket 16356).

Los documentos fiscales solo admiten 2 decimales en el precio unitario. En
una instalación nueva, data/decimal_precision.xml pone "Product Price" y
"Foreign Product Price" en 2; en una actualización Odoo no reescribe esos
registros (sus xmlids son noupdate), así que aquí se ponen en 2 una sola vez
para las bases donde el módulo ya estaba instalado.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["decimal.precision"]._set_fiscal_price_digits()
