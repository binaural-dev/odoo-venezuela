"""TA-74966: rellena sale_order.foreign_rate_date en las ordenes existentes.

foreign_rate_date guarda la fecha de la que salio la tasa de la orden, y es la
que se hereda a invoice_date de la factura. En las ordenes creadas antes de
este cambio el campo queda NULL, y aunque _compute_foreign_price y
_prepare_invoice caen a date_order como respaldo, ese respaldo no siempre es
correcto: el core reescribe date_order con la fecha de confirmacion
(_prepare_confirmation_values), asi que en una orden con la tasa congelada
date_order ya no es la fecha de su tasa.

Criterio:

  * Compania con "Update sale order rate using date order" ACTIVO (tasa viva):
    la tasa se recalculo con date_order, asi que date_order ES la fecha de la
    tasa. Valor exacto.

  * Compania con la opcion INACTIVA (tasa congelada): la tasa se fijo la
    primera vez que se calculo, es decir al crear la orden. create_date es la
    mejor aproximacion disponible; date_order ya pudo moverse al confirmar.

Solo se tocan las ordenes que todavia no se han facturado por completo: son
las unicas donde el valor va a usarse. En las ya facturadas se deja NULL, con
lo que siguen cayendo a date_order y conservan exactamente el comportamiento
que tenian antes de esta version.
"""


def migrate(cr, installed_version):
    cr.execute(
        """
        UPDATE sale_order so
        SET foreign_rate_date = CASE
                WHEN COALESCE(rc.update_sale_order_rate_using_date_order, FALSE)
                    THEN so.date_order::date
                ELSE COALESCE(so.create_date, so.date_order)::date
            END
        FROM res_company rc
        WHERE rc.id = so.company_id
          AND so.foreign_rate_date IS NULL
          AND so.date_order IS NOT NULL
          AND so.state IN ('draft', 'sent', 'sale')
          AND COALESCE(so.invoice_status, 'no') <> 'invoiced'
        """
    )
