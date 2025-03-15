Este modulo permite hacer las conexiones a la maquina fiscal desde el modulo de Punto de Venta

## Funcionalidades

* Permite descargar el Libro de ventas Agrupado por Rango de Facturas
* En caso de ser un Recibo este no manda a imprimirse el documento
* Se creo wizard para imprimir el LIbro de Ventas Agrupados
* Al momento de tener el check de la caja registradora intentara abrirla en cuanto se seleccione un metodo de pago con el tipo de diario efectivo y en cuanto se haga click en el boton de control de efectivo
* Se elimino el boton de abrir caja nativa de odoo.
  configuracion

## Campos

### Asiento Contable (account.move)

* Agrega la caja en la que fue facturada
* Agrega el tipo de registro para el libro si REG, o ANU

### Terminal Punto de Venta (pos.config)

* Agrega configuracion para seleccionar la Maquina fiscal

### pedido de venta (pos.order)

* Reporte Z
* Numero de Documento
* Maquina fiscal usada

### Metodo de pago (pos.payment.method)

* Codigo de metodo de pago para la maquina fiscal

### Sesion de Punto de Venta (pos.session)

* Serial de la maquina fiscal
* Maquina fiscal 
* Reporte Z

## Interfaz de POS

Permite Realizar Reportes X, Z

