#Binaural Vendedores

Este modulo se encarga de agregar una función extra a los empleados de la empresa que es marcarlos
como Vendedores.

Este añade los siguientes campos:

##Configuraciones:

* Vendedor por defecto
* Multiples vendedores

## Validaciones

* Al agregar uno o más vendedores en la ficha del contacto se verificará de que la configuración
  de Multiples vendedores esté encendida para así identificar cuantos vendedores debe de asignar.
* Al confirmar un presupuesto se le agregará el vendedor que tiene asignado y sí posee más de un 
  vendedor y la configuración de Multiples vendedores está apagado, no le permitirá continuar con
  el flujo.
* al confirmar una Factura de cliente  se le asignará el vendedor al seleccionar el cliente, en 
  dado caso que posea más de uno este informará que vendedores puede seleccionar.

##Ficha de empleados (hr.employee)

* Es vendedor

##Ficha de contacto (res.partner)

* Vendedores

##Orden de venta (sale.order)

* Vendedor

##Facturación (account.move)

* Vendedor