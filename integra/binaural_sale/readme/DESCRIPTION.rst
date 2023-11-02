Este modulo agrega funcionalidades que permiten manejar el proceso de ventas en Venezuela
utilizando moneda extranjera.


Campos agregados a modelos existentes
"""""""""""""""""""""""""""""""""""""

* Línea de Tarifa (product.pricelist.item) / Factura (account.move).

  * price_without_tax: Precio sin impuesto.
  * price_with_tax: Precio + IVA.

* Pedido de venta (sale.order).

  * foreign_currency_id: Moneda Alterna.
  * vat: RIF.
  * foreign_rate: Tasa Alterna.
  * foreign_inverse_rate: Tasa Inversa Alterna.
  * total_taxed: Total Gravado.
  * foreign_taxable_income: Base imponible alterna.
  * foreign_total_billed: Total alterno facturado.

* Línea de pedido de venta (sale.order.line).

  * foreign_currency_id: Moneda Alterna.
  * foreign_rate: Tasa Alterna.
  * foreign_inverse_rate: Tasa Inversa Alterna.
  * foreign_price: Precio Alterno.
  * foreign_subtotal: Subtotal Alterno.

Configuraciones
"""""""""""""""
* Compañía (res.company).

  * use_invoice_rate_from_sale_order: Usar la tasa de la orden de venta en la factura.
  * update_sale_order_rate_using_date_order: Actualizar la tasa de la orden de venta usando la fecha.
  * not_allow_sell_products: No permitir vender inventario en cero.

Funcionalidades
"""""""""""""""

* Se agrega el símbolo de la moneda alterna en los campos de moneda en la orden de venta.
* Crear varias facturas a partir de una orden de venta si esta excede el límite de líneas por factura.

Validaciones
""""""""""""

* No permitir agregar más de un impuesto por línea de pedido de venta (configuración).
* No permitir vender productos con inventario en cero (configuración).
