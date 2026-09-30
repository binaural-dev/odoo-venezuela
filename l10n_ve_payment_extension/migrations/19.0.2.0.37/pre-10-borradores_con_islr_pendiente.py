"""Marca generate_islr_retention en los borradores que en 17 iban a generar retención de ISLR.

Qué: crea account_move.generate_islr_retention y la pone en True en las facturas en borrador sin
    comprobante de ISLR que ya tienen líneas de retención de ISLR (con concepto de pago o de una
    retención de tipo islr, el mismo dominio de retention_islr_line_ids en 17).

Por qué: en 17, action_post creaba la retención de ISLR cuando la factura tenía esas líneas y no
    tenía comprobante. En 19 sólo la crea si generate_islr_retention está marcado, un campo nuevo
    que nace en False. A lo ya publicado no le afecta, porque tiene su comprobante. Pero un
    borrador que en 17 ya tenía cargadas sus líneas de ISLR se publicaría en 19 sin retención.
    En las bases v17 que tenemos hay un caso, en idv.

Qué pasa si no corre: esos borradores, al publicarse después de migrar, no generan la retención
    de ISLR y hay que hacerla a mano.

Cómo revertirlo: desmarcar el campo en la factura antes de publicarla.

Tarea: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

from odoo.upgrade import util


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return
    if not util.create_column(cr, "account_move", "generate_islr_retention", "boolean"):
        return
    if not util.table_exists(cr, "account_retention_line"):
        return

    cr.execute(
        """
        UPDATE account_move m
           SET generate_islr_retention = TRUE
         WHERE m.state = 'draft'
           AND m.islr_voucher_number IS NULL
           AND EXISTS (
                SELECT 1
                  FROM account_retention_line l
             LEFT JOIN account_retention r ON r.id = l.retention_id
                 WHERE l.move_id = m.id
                   AND (l.payment_concept_id IS NOT NULL OR r.type_retention = 'islr')
           )
        """
    )
    if cr.rowcount:
        util.add_to_migration_reports(
            f"Retenciones: {cr.rowcount} facturas en borrador con líneas de ISLR de 17 quedan con "
            "\"Generar retención de ISLR\" marcado, para que al publicarlas se cree la retención como en 17.",
            category="Binaural · Contabilidad",
        )
