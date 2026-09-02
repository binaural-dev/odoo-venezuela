from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round


class AccountMove(models.Model):
    _inherit = "account.move"

    convert_currency_from_sale_order = fields.Boolean(
        related="company_id.convert_currency_from_sale_order",
    )

    def _get_sale_conversion_pricelist_rule(self, line):
        """Regla de tarifa que pisaria la conversion de esta linea, si la hay.

        `account_invoice_pricelist` (OCA) recalcula price_unit desde la tarifa
        de la factura, asi que si esa tarifa define una regla para el producto
        habria dos logicas compitiendo por el mismo campo. Este helper la
        detecta para poder abortar en vez de dejar que una pise a la otra.

        El acceso es defensivo: `pricelist_id` en account.move lo agrega
        `account_invoice_pricelist`, que no es dependencia de este modulo. Si
        no esta instalado no hay reglas que respetar y la conversion procede.
        """
        self.ensure_one()
        if "pricelist_id" not in self._fields:
            return False
        pricelist = self.pricelist_id
        if not pricelist or not line.product_id:
            return False
        return pricelist._get_product_rule(
            line.product_id,
            quantity=line.quantity or 1.0,
            uom=line.product_uom_id,
            date=self.invoice_date or fields.Date.context_today(self),
        )

    @api.onchange("currency_id", "invoice_date")
    def _onchange_currency_sync_from_so(self):
        """Convierte los precios unitarios desde el Pedido de Ventas cuando
        cambia la moneda o la fecha de la factura.

        Espejo de lo que hace binaural_purchase con la Orden de Compra, con la
        diferencia de que en ventas el enlace es `sale_line_ids`, un Many2many:
        una linea de factura puede proceder de varias lineas de venta. Solo se
        convierten las lineas con un origen inequivoco (exactamente una linea
        de venta); las agrupadas se dejan como estan porque no hay un precio
        de origen unico del que partir.

        La conversion usa la fecha de la factura, que en esta localizacion es
        la fecha de la tasa (la fecha visible del documento es
        invoice_date_display).
        """
        if not self.invoice_origin or not self.currency_id:
            return

        # No se compara contra _origin para decidir si hay algo que hacer: al
        # volver a la moneda de partida dentro del mismo borrador (USD -> VES
        # -> USD) el valor coincidiria con el guardado y se saldria sin
        # recalcular, dejando el precio de la otra moneda. El onchange solo se
        # dispara cuando cambia currency_id o invoice_date, asi que recalcular
        # siempre es correcto: si la moneda vuelve a ser la de la orden, la
        # primera rama restituye su precio original.
        # Solo facturas de cliente. Las notas de credito y debito se emiten
        # siempre en base a su factura de origen, asi que recalcularlas desde
        # el pedido de ventas las desalinearia del documento que rectifican.
        if not (
            self.move_type == "out_invoice"
            and self.company_id.convert_currency_from_sale_order
        ):
            return

        invoice_date = self.invoice_date or fields.Date.context_today(self)
        precision = self.env["decimal.precision"].precision_get("Product Price")

        # Primero se validan todas las lineas: si alguna tiene regla de tarifa
        # no se convierte ninguna, para no dejar la factura a medio recalcular.
        blocking = []
        for line in self.invoice_line_ids:
            if len(line.sale_line_ids) != 1:
                continue
            if line.product_id.type not in ("consu", "service"):
                continue
            if self._get_sale_conversion_pricelist_rule(line):
                blocking.append(line.product_id.display_name)

        if blocking:
            # dict.fromkeys en vez de set(): con lineas duplicadas del mismo
            # producto (mismo precio y cantidad, cada una con su propia
            # sale_line_ids), el mismo nombre podia agregarse mas de una vez
            # y el mensaje de error repetia el producto. dict.fromkeys quita
            # los duplicados preservando el orden de aparicion.
            blocking = list(dict.fromkeys(blocking))
            raise UserError(
                _(
                    "The pricelist %(pricelist)s defines a rule for the "
                    "following products, so their price cannot be recalculated "
                    "from the sale order: %(products)s.\n\n"
                    "Both mechanisms set the same unit price and one would "
                    "override the other. Either remove the pricelist rule or "
                    "disable \"Convert Currency From Sale Order\".",
                    pricelist=self.pricelist_id.display_name,
                    products=", ".join(blocking),
                )
            )

        for line in self.invoice_line_ids:
            if len(line.sale_line_ids) != 1:
                continue

            so_line = line.sale_line_ids
            if line.product_id.type not in ("consu", "service"):
                continue

            order = so_line.order_id

            if self.currency_id == order.currency_id:
                # Misma moneda que la orden: no hay nada que convertir, la
                # fecha no interviene.
                new_price_unit = so_line.price_unit
            else:
                # Cualquier otra moneda -- incluida la alterna de la
                # compania -- convierte con invoice_date, la fecha de LA
                # FACTURA. No se usa so_line.foreign_price aqui a proposito:
                # ese campo esta calculado con la fecha de la ORDEN
                # (order.foreign_rate_date), que puede no coincidir con
                # invoice_date -- convert_currency_from_sale_order es un flag
                # independiente de use_invoice_rate_from_sale_order, asi que
                # la factura puede tener su propia fecha. El ticket pide
                # convertir "a la tasa de la Factura", no a la de la orden.
                new_price_unit = float_round(
                    order.currency_id._convert(
                        so_line.price_unit,
                        self.currency_id,
                        self.company_id,
                        invoice_date,
                        round=False,
                    ),
                    precision_digits=precision,
                )

            # Solo se toca price_unit: foreign_price es un campo calculado que
            # depende de el y de la fecha, asi que se recalcula solo.
            line.price_unit = new_price_unit
