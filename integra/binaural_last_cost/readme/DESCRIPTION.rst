Este módulo agrega el uso del último costo en los productos para realizar operaciones.


Campos agregados a modelos existentes
"""""""""""""""""""""""""""""""""""""

* Variantes de producto (product.product).

  * latest_standard_price: Último costo del producto.
  * last_latest_standard_price: Último costo del producto antes de ser modificado.
  * value_total_last_cost: Calcula el último costo por la cantidad del producto.


* Plantilla del producto (product.template).

  * update_last_cost: Check para actualizar el último costo.
  * variants_are_active: Verifica si las variantes del producto están activas.
  * latest_standard_price: Último costo del producto.
  * last_latest_standard_price: Último costo del producto antes de ser modificado.
  
* Líneas de compra (purchase.order.line).

  * latest_standard_price: Último costo del producto.
  * update_latest_standard_price: Check para actualizar el último costo.
  * price_per_udm: Último costo del producto por unidad de medida.

Funcionalidades
"""""""""""""""

* Se agrega el campo de último costo en los productos.
* Las compras de productos vienen con el precio del último costo.

