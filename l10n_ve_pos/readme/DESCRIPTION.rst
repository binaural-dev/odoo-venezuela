#Binaural POS

Este modulo se encarga de realizar los calculos y guardar los montos en la moneda alterna 
registrada en la configuracion asi como tambien validaciones.

Este añade los siguientes campos:

##Configuraciones:

* Impuestos incluidos (No alternar impuestos entre facturas/recibos)
* Facturar siempre : Seleccionar por defecto facturas o recibos para generar asientos contables
* Mantener Factura: Al momento de cambiar el tipo de documento en el pos, este se mantiene para la proxima orden
* Mostrar cantidades disponibles en stock
* Mostrar solamente los productos disponibles: Eliminar automáticamente los productos sin disponibilidad del POS
* Cantidad en 0 : No permitir ventas si no hay disponibilidad suficiente
* (res.group) permitir descuentos
* (res.group) Grupo para administrar cantidades en POS
* (res.group) Grupo para Cambiar el precio en POS

## Validaciones

* Editar el estatus de los asientos contables asociados al POS (Punto de Venta) si la sesiona la que corresponde esta abierta

##Terminal de Punto de venta (pos.config)

* Moneda alterna
* Tasa Moneda alterna inversa
* Tasa de moneda alterna

##Orden de POS (pos.order)

* Moneda alterna
* Monto total en moneda alterna
* Tasa de moneda alterna
* Se refleja la cantidad de productos a ordenar

##Pagos (pos.payment)

* Tasa de moneda alterna
* Monto en moneda alterna
* Moneda alterna

##Metodos de pago

* Es moneda alterna? Este permite saber si la representacion del monto del 
  pago se vera reflejado en # o en bs

----------------------------------------

#Interfaz de POS

* Se agrega el prefijo del documento de identidad en las listas de clientes y al momento de registrarlo
* Se creo flujo para buscar cedulas en caso de que no encuentre una registrada en el sistema las busca
  en el CNE y lo ingresa automaticamente al area de registro
* Se Visualizan los Montos alternos como Precio unitario, Monto de impuestos, Monto total,
  tasa, Monto adeudado
* Se refleja en la pantalla de pagos el documento de identidad del cliente
* Se refleja en las lineas de la orden si el producto contiene o no IVA
* Al momento de una nota de credito,se agrega a la pantalla de pagos un boton para visualizar 
  los metodos de pago y montos con los que fueron pagados 

----------------------------------------

* El reporte detallado se reorganizo para mostrar principalmente los pagos
