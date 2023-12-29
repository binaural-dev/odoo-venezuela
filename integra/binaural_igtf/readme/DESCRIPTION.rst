Este modulo agrega el uso IGTF para el pago de las facturas del sistema.


Campos agregados a modelos existentes
"""""""""""""""""""""""""""""""""""""

* Asiento contables (account.move).

  * default_is_igtf_config: Booleano para validar configuraciones de IGTF.
  * payment_igtf_id: Relacion del pago con IGTF del asiento contable.
  
*  Pagos (account.payment).

  * is_igtf: Booleano para validar configuraciones de IGTF.
  * is_igtf_on_foreign_exchange: Booleano para validar si el diario y la moneda es en dolares y aplica IGTF.
  * igtf_percentage: Porcentaje del IGTF calculado.
  * igtf_amount: Monto del IGTF calculado.
  * amount_with_igtf: Monto del IGTF calculado mas el monto del pago.

*  Diarios (account.journal).

  * default_is_igtf_config: Booleano para validar configuraciones de IGTF.
  * is_igtf: Booleano para validar que el diario aplica IGTF.

Funcionalidades
"""""""""""""""

* Se calcula el IGTF de los pagos que sean en dolares y el diario aplique IGTF.
* Crea linea de IGTF en el asiento del pago para conciliar a la factura directamente.
* Se toma en cuenta flujo de pagos normal y desde el wizard (pagos directos de facturas)