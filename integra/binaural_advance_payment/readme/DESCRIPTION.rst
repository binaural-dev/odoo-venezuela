Este modulo agrega el uso Anticipos para el pago de las facturas del sistema.


Campos agregados a modelos existentes
"""""""""""""""""""""""""""""""""""""

* Apuntes contables (account.move.line).

  * payment_id_advance: Anticipo.

* Asiento contables (account.move).

  * outstanding_credits_debits_widget_advance_payment: Widget de anticipos.
  * invoice_outstanding_credits_debits_widget_advance_payment: Widget de anticipos.
  
*  Pagos (account.payment).

  * is_advance_payment: Es un anticipo.

Configuraciones
"""""""""""""""
* Compañía (res.company).

  * advance_customer_account_id: Cuenta de anticipos para clientes (pasivo circulante)).
  * advance_supplier_account_id: Cuenta de anticipos para proveedores (activo circulante).

Funcionalidades
"""""""""""""""

* Se agrega el Widget de los Anticipos que te dejaran conciliarlos en las facturas.
* Crear pagos como Anticipos para ser usados en futuras facturas.

Validaciones
""""""""""""

* El Widget de anticipos existira en las facturas cuando haya saldo disponible de Anticipo en el cliente o proveedor.
* Al registrar un anticipo este tiene que se de tipo 'Banco' o 'Efectivo'.

