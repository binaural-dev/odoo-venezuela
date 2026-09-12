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

POR QUE ES UNA MIGRACION `pre-` Y NO `post-`
============================================

foreign_rate_date es un campo calculado almacenado que comparte
compute="_compute_rate" con foreign_rate (que lleva tracking=True) y con
foreign_inverse_rate.

Cuando el ORM crea la columna de un calculado almacenado marca TODOS los
registros existentes para computar -- odoo/orm/models.py, _auto_init:

    new = field.update_db(self, columns)
    if new and field.compute:
        fields_to_compute.append(field)
    ...
    for field in fields_to_compute:
        self.env.add_to_compute(field, records)   # records = toda la tabla

y al ejecutarse _compute_rate se asignan los tres campos que comparten el
metodo. En las companias con "Update sale order rate using date order" activo
no hay guard que lo pare, asi que las ordenes historicas quedarian con la tasa
reescrita a partir de date_order -- que el core ya movio a la fecha de
confirmacion -- y con un mensaje en el chatter por cada una, al ser
foreign_rate un campo con tracking.

Creando la columna aqui, antes de que el ORM cargue el modelo, update_db la
encuentra existente, no la trata como nueva y no dispara ese recompute. La
version anterior de este script era `post-`: corria despues del recompute, de
modo que reparaba foreign_rate_date pero no el reescrito colateral de la tasa.
"""


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'sale_order'
          AND column_name = 'foreign_rate_date'
        """
    )
    if not cr.fetchone():
        cr.execute("ALTER TABLE sale_order ADD COLUMN foreign_rate_date date")

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
