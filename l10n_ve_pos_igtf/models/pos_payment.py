from odoo import fields, models


class PosPayment(models.Model):
    _inherit = "pos.payment"

    include_igtf = fields.Boolean()
    igtf_amount = fields.Float()
    foreign_igtf_amount = fields.Float()

    # NO declarar include_igtf / igtf_amount / foreign_igtf_amount en
    # _load_pos_data_fields: los volvería campos REACTIVOS y update_igtf() los
    # reescribe en cada recálculo, marcando los pagos `_dirty` y colgando el
    # POS en un bucle de render/sync. Los inyecta `PosOrder.serializeForORM`
    # (order_model.js) en los comandos de payment_ids, porque las líneas hijas
    # se serializan por recursión directa (``deepSerialization``) y nunca pasan
    # por el `serializeForORM` del modelo JS de pos.payment.
