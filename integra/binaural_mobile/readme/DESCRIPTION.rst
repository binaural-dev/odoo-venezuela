#Binaural Movil

Este modulo se encarga de crearle espacios para la ventas de los vendedores, crear presupuestos, procesar pagos a facturas y configuraciones para los vendedores asi como tambien validaciones.

Este añade los siguientes campos:

##Configuraciones:

* Tipos de productos visualizados por los vendedores (Almacenable, Servicio, Consumible)
* Las retenciones creadas quedan en borrador o publicadas
* Orden para pagar facturas
* Vista de productos predeterminada para vendedores (Lista, Cuadricula)
* Procesar pagos (Total o Parcial)
* Métodos de pagos usados en la app
* Diario fiscal para la app
* Diario no fiscal para la app
* Diario de ventas disponibles para la app
* (res.group) Grupo para vendedores que puedan editar tarifas
* (res.group) Grupo para vendedores que puedan crear contactos
* Activar opcion de sin exitencia continuar venta en la configuraciones de sitio web(Solo si vendera productos que no tiene existencia)
* Incluir impuestos en el Precio y Subtotal de la linea del Presupuesto
* (Modo debug) No cambiar el impuesto al cambiar Requiere Factuar : Impuestos incluidos Siempre

## Validaciones

* Cualquier pago que venga proveniente de la app se saltará la validación del no conciliar pagos con distintos diarios
* Productos que se le mostrarán al vendedor por configuración
* Sí la configuración de empaquetado está activado, validará que cuando un producto tenga un empaquetado en la lista por si se activa el empaquetado en la ficha del producto 
* Al tener apagado la opcion de sin existencia continuar venta, no podra hacer busqueda de producto, tampoco le permitira vender mas de la cantidad disponible

##Pagos (account.payment)

* pagos de la app

##Ventas (sale.order)

* Incluye impuestos
* Diario

##Pagos de la app (payment.mobile)

* Cliente
* Monto en moneda base
* Vendedor
* Estado del pago
* Compañia
* Comprobante de pago
* Moneda base
* Fiscal 
* Pago verificado
* Líneas de pago
* Métodos de pago

##Líneas de pago de la app (payment.mobile.line)

* Pago relacionado
* Factura relacionada
* Diario del pago
* Cliente del pago
* Moneda base
* Moneda alterna
* Monto del pago
* Monto del pago en moneda alterna
* Monto conciliado a la factura
* Monto conciliado a la factura en moneda alterna
* Fecha de pago
* Uso anticipo
* Tasa de moneda alterna

##Métodos de pago de la app (payment.mobile.methods)

* Diario del pago
* Monto del pago
* Moneda del pago

##Comprobante de pago de la app (payment.mobile.proof)

* Nombre del archivo
* Archivo Comprobante

----------------------------------------

#Interfaz del vendedor

* Se agrego desde el menu de portal que el vendedor pueda crear presupuestos y crear pagos a facturas
* Se agrego que al vendedor le salgan disponibles a la vista los tipos de productos que estén configurados en el sistema
* Se Visualizan los presupuestos, facturas y pagos hechos por el vendedor de la sesión

----------------------------------------
