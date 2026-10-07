"""Las opciones de combo que ya tenían ítems con un tipo distinto de
`principal` (reparto heredado de binaural_clinics_sale) conservan ese reparto.
"""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE product_combo
           SET price_distribution = 'by_item_type'
         WHERE id IN (
               SELECT combo_id
                 FROM product_combo_item
                WHERE item_type IS NOT NULL
                  AND item_type != 'principal'
         )
        """
    )
