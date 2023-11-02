Este modulo permite realizar los calculos de igtf dentro del Punto de Venta.

## Funcionamiento

Al momento de avanzar a nuestra pantalla de pagos, si uno de los metodos de pagos esta configurado
con IGTF, este al ingresar un monto calcula automaticamente el monto a de IGTF a pagar. 

Contablemente al pago en $ se le resta el monto del igtf. es decir siempre se restara el igtf al 
pago en Dolares.

Mientras se realiza la operacion se va mostrando en el recuadro del pago el monto del IGTF a pagar
en tiempo real

En caso de ser una factura este solicitara IGTF, en caso de ser una nota de Entrega / Recibo este no
solicitara IGTF

##Campos:

### Terminal de Punto de Venta (pos.config)

* Porcentaje de IGTF (no es visible ya que se usa para rescatarlo en POS)

### Orden (pos.order)

* Monto de igtf
* Monto de Base imponible de IGTF

### Pagos (pos.payment)

* Identificacion si el pago incluye el IGTF
* Monto del IGTF pagado dentro del pago
* Monto alterno del IGTF pagado dentro del pago

### Metodos de Pago (pos.payment.method)

* Aplica IGTF

## Validaciones:

* Si no se tiene configurado la cuenta de IGTF de clientes en la configuracion este no permitira
  abrir la caja del POS


