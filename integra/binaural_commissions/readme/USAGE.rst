Para crear una politica se debe dirigir a Contabilidad > Ajustes > Politica de Comisión.

Esta politica puede aplicada en base a productos, clientes o una politica general, en caso de ser 
de tipo producto, este despliega una lista de items, en la que se pueden aplicar a Productos especificos,
el conjunto de productos en una marca o el conjunto de productos dentro de una categoria.

En orden de prioridad se asignan:

* Producto 
Producto
Marca
Categoria
* Cliente
* General

En la configuracion de la politica se colocan los rangos de dias

de 0 a 3 dias = 3% de comision
de 4 a 6 dias = 2% de comision
de 7 al infinito = 1% de comision

Al momento de confirmar el presupuesto, en este se almacena la configuracion al dia de las comisiones,
es decir, se almacenan los rangos de dias correspendientes al producto, el cliente o la politica general. 

Al momento de crear la Factura, se envian las configuraciones a ella, y dependiendo de la cantidad de dias
de diferencia entre (dependiendo de la configuracion) Fecha de la Factura/Fecha de recepcion hasta 
La fecha del Primer pago/la fecha del ultimo pago (omitiendo retenciones).

En caso de que se pague en el rango de 3 dias, aplicaria un 3% de comisión

Al seleccionar multiples facturas, se selecciona Accion > Pagar Comisiones, y te desplega un 
Popup donde te muestra informacion y como desea pagar la comision.
