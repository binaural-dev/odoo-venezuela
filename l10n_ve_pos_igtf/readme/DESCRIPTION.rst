Este modulo permite realizar los calculos de igtf dentro del Punto de Venta.

## Funcionamiento

Al momento de avanzar a nuestra pantalla de pagos, si uno de los metodos de pagos esta configurado
con IGTF, este al ingresar un monto calcula automaticamente el monto a de IGTF a pagar. 

Contablemente la factura solo cobra su base: el pago en divisa lleva el monto completo (base mas
IGTF), y el IGTF sale del cobro del cliente hacia la cuenta de IGTF de clientes en un asiento
propio, que se concilia junto con el pago y la factura. El asiento lleva el monto alterno del IGTF
y la tasa de la venta; en una nota de credito se invierte.

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

### Configuracion de moneda del metodo de pago (pos.payment.method.currency)

* Aplica IGTF: se marca por metodo de pago y moneda (por ejemplo Efectivo en $, Efectivo en EUR y
  Zelle en $). Un pago en Bs. no genera IGTF.

## Validaciones:

* Si no se tiene configurado la cuenta de IGTF de clientes en la configuracion este no permitira
  abrir la caja del POS (con algun metodo de pago y moneda que aplique IGTF)


