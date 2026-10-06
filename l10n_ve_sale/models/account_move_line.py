from odoo import api, fields, models

import logging
_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # -- Combo hierarchy --------------------------------------------------

    combo_parent_line_id = fields.Many2one(
        'account.move.line',
        string="Sección / Subsección Padre",
        # Mismo criterio que sale.order.line: 'set null' en vez de 'cascade'
        # para no disparar DELETEs contra ids aún no guardados en la BD.
        ondelete='set null',
        index=True,
    )
    combo_root_line_id = fields.Many2one(
        'account.move.line',
        string="Contenedor Combo Raíz",
        ondelete='set null',
        index=True,
    )
    combo_tagged = fields.Boolean(
        string="Pertenece a un combo",
        default=False,
        help=(
            "Espejo booleano de combo_root_line_id / combo_parent_line_id. "
            "Permite al JS filtrar líneas del combo antes de que el formulario "
            "esté guardado (un Many2one a otro registro sin guardar no llega "
            "resuelto confiablemente a record.data)."
        ),
    )
    combo_item_qty_per_combo = fields.Float(
        string="Cantidad elegida por combo",
        default=1.0,
        help=(
            "Unidades de este producto elegidas en el wizard por cada unidad "
            "del combo. Se usa para recalcular quantity cuando la cantidad del "
            "combo raíz cambia."
        ),
    )

    # Campo efímero (no almacenado) que el wizard escribe y el onchange lee
    selected_combo_items = fields.Char(store=False)

    # Related para que el JS pueda detectar combos sin cargar el producto
    product_template_id = fields.Many2one(
        related='product_id.product_tmpl_id',
        store=False,
        string="Plantilla de Producto",
    )
    product_type = fields.Selection(
        related='product_id.type',
        store=False,
        string="Tipo de Producto",
    )
