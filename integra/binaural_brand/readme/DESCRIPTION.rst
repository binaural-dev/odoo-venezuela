#Binaural Marca

Este modulo se encarga de asignarle una marca a los productos desde la ficha de producto, reportes 
de inventario compras y ventas.

Modelos agregado:

##Marca de producto (product.brand)

* Nombre
* Compañia 
* Activo

Este añade los siguientes campos a los modelos existentes:

## Asientos contables (account.move.line), Líneas de orden de compra  (purchase.order.line), Líneas de orden de venta (sale.order.line), Líneas de movimiento de inventario (stock.move.line)

* Marca del producto

##Punto de pedido del almacén de existencias (stock.warehouse.orderpoint), Ficha de producto (product.template), Reporte de ventas (sale.report), Movimiento en inventario (stock.move), Picking de Inventario(stock.picking), Cantidad en Inventario (stock.quant)

* Marca del producto
