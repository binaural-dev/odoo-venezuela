=====================
Venezuela - Ventas
=====================

Adapta el módulo de Ventas de Odoo a la operación en Venezuela: montos en
moneda alterna sobre los pedidos, control de la tasa de cambio a lo largo del
ciclo presupuesto → pedido → factura, y una serie de controles de negocio
sobre la confirmación de pedidos.

Depende de ``l10n_ve_accountant`` (a través de ``l10n_ve_invoice``), que es
donde vive el cálculo de moneda alterna de los documentos contables.


Moneda alterna en los pedidos
=============================

Cada pedido lleva su tasa y los montos equivalentes en la moneda alterna de la
compañía (normalmente USD, con la compañía en VES).

**En la cabecera (**``sale.order``**)**

:``foreign_rate`` / ``foreign_inverse_rate``: tasa del pedido.
:``foreign_rate_date``: fecha de la que se tomó esa tasa. **No** es
   ``date_order``: Odoo reescribe ``date_order`` con la fecha de confirmación
   (``_prepare_confirmation_values``), mientras que este campo conserva la
   fecha de la que realmente salió la tasa. Es la que heredan las líneas y la
   factura. Está oculto en el formulario.
:``manually_set_rate``: la tasa viene fijada desde fuera y no se recalcula.
:``foreign_taxable_income`` / ``foreign_untaxed_total`` / ``foreign_total_billed``:
   base imponible, subtotal y total en moneda alterna.
:``amount_untaxed_total_signed`` / ``amount_total_signed``: los mismos totales
   en moneda de la compañía.

**En las líneas (**``sale.order.line``**)**

:``foreign_price``: precio unitario en moneda alterna.
:``foreign_subtotal``: subtotal en moneda alterna.

Todos los montos alternos se calculan con ``currency._convert()`` a la fecha
de ``foreign_rate_date``. Nunca se multiplica ni se divide a mano por una
tasa: la migración de Odoo 17 (compañía en USD) a 19 (compañía en VES)
intercambió el significado de ``foreign_rate`` y ``foreign_inverse_rate``, y
una multiplicación manual depende de recordar cuál aplica y en qué dirección.

``foreign_price`` se redondea a la precisión decimal ``Foreign Product Price``,
no a los decimales de la moneda: un precio unitario pequeño colapsaría a cero
y el subtotal arrastraría ese cero multiplicado por la cantidad.

``foreign_subtotal`` pasa por ``compute_all`` cuando la línea tiene impuestos,
de modo que el subtotal sea la base real —descontando el impuesto si va
incluido en el precio— y quede redondeado a la moneda alterna.

Los totales del documento se leen de ``tax_totals``, que ya los calcula, en
lugar de convertirlos por segunda vez.


Configuración
=============

*Ajustes → Ventas → sección Binaural*

Actualizar la tasa del pedido con la fecha del pedido
----------------------------------------------------

``update_sale_order_rate_using_date_order`` (desactivada por defecto)

:Activada: la tasa del pedido sigue a ``date_order`` y se refresca cuando ésta
   cambia.
:Desactivada: la tasa se fija la primera vez y queda **congelada**. Es el caso
   del presupuesto que se negocia durante varios días sin que el monto en
   divisa se mueva. ``foreign_rate_date`` conserva la fecha original aunque la
   confirmación mueva ``date_order``, de modo que las líneas siguen
   convirtiendo con la tasa congelada.

Usar la tasa del pedido en la factura
-------------------------------------

``use_invoice_rate_from_sale_order`` (desactivada por defecto)

:Activada: la factura hereda la **fecha** de la tasa del pedido —se pasa como
   ``invoice_date``, que en esta localización es la fecha de la tasa— de modo
   que ambos documentos convierten con la misma tasa.
:Desactivada: la factura usa la tasa de su propia fecha.

Convertir moneda desde el pedido de ventas
------------------------------------------

``convert_currency_from_sale_order`` (desactivada por defecto)

Al cambiar la moneda o la fecha de una **factura de cliente** generada desde
un pedido, recalcula los precios unitarios a partir del pedido de origen,
usando la tasa de la factura.

* Se aplica solo a ``out_invoice``. Las notas de crédito y débito se emiten
  siempre en base a su factura de origen, así que recalcularlas desde el
  pedido las desalinearía del documento que rectifican.
* Funciona en ambos sentidos y con cualquier moneda: de moneda extranjera a
  bolívares, de bolívares a moneda extranjera, y hacia una tercera moneda.
* La tasa que manda es la de ``invoice_date`` de **la factura**, no la del
  pedido. Es independiente de ``use_invoice_rate_from_sale_order``: ese flag
  solo decide qué fecha hereda la factura al crearse; una vez creada, si el
  usuario cambia ``invoice_date`` a mano, el recálculo respeta ese cambio.
* Cada línea se empareja con su línea de pedido por ``sale_line_ids``. Cuando
  una línea de factura agrupa varias líneas de venta no hay un precio de
  origen único, así que se deja como está. Lo mismo si la línea es huérfana
  (su línea de pedido de origen ya no existe) o no tiene producto (fue
  archivado, o es una sección/nota).
* Los productos tipo combo no necesitan tratamiento especial: la línea del
  combo padre llega sin producto (es un encabezado de sección) y se salta
  sola; cada ítem elegido dentro del combo es una línea de producto normal,
  con su propia línea de pedido de origen, y se convierte igual que cualquier
  otra.
* Solo modifica ``price_unit``. ``foreign_price`` es calculado y se actualiza
  solo; el descuento de la línea no se toca.

**Interacción con las listas de precios.** Si está instalado
``account_invoice_pricelist``, la factura lleva tarifa y esa tarifa también
fija ``price_unit`` (``_compute_price_unit``). Serían dos lógicas escribiendo
el mismo campo. Por eso, si la tarifa de la factura define una regla para
alguno de los productos, el recálculo **se aborta con un error** en lugar de
pisarla, sin convertir ninguna línea. Hay que elegir: o se quita la regla de
la tarifa, o se desactiva esta opción.

En la interfaz, la moneda de la factura la impone la tarifa y no se puede
cambiar por separado (``_check_currency``), así que el flujo real es
**cambiar la Tarifa**: la moneda se ajusta sola y el recálculo se dispara en
cascada.

Otros controles
---------------

:``not_allow_sell_products``: impide confirmar pedidos con productos
   almacenables sin existencias suficientes.
:``block_order_invoice_payment_state`` y
   ``block_order_invoice_total_amount_overdue``: bloquean la confirmación
   según el estado de pago y el monto vencido del cliente.
:``are_sale_lines_limited`` y ``maximum_sales_line_limit``: limitan el número
   de líneas de un presupuesto.


Otras funcionalidades
=====================

* ``vat`` en el pedido, compuesto con el prefijo del RIF del cliente.
* Campos ``address`` y ``mobile`` del cliente accesibles desde el pedido.
* ``invoiced`` por línea y estado ``partially_billed`` en ``invoice_status``.
* Informes de ventas con los montos en moneda alterna.


Migraciones
===========

``19.0.1.0.6`` — rellena ``foreign_rate_date`` en los pedidos existentes que
todavía no se han facturado: ``date_order`` si la tasa está viva y
``create_date`` si está congelada. Los ya facturados quedan sin valor y
conservan el comportamiento anterior.


Pruebas
=======

La documentación viva del módulo son sus pruebas. Cada una está escrita para
fallar si se revierte el comportamiento que verifica:

:``tests/test_ta74966_currency.py``: fecha de la tasa, tasa congelada que
   sobrevive a la confirmación, herencia de la fecha a la factura, totales
   desde ``tax_totals``, precisión y multi-compañía.
:``tests/test_ta80647_invoice_currency.py``: recálculo de la factura desde el
   pedido en ambos sentidos, con terceras monedas y cubriendo las tres ramas
   de conversión por separado, siempre a la fecha de la factura (no la del
   pedido); bloqueo por regla de tarifa sin repetir productos en el mensaje;
   exclusión de las notas de crédito; casos borde (duplicados, línea
   huérfana, producto archivado, reordenamiento, productos tipo combo); y el
   flujo real de la interfaz cambiando la tarifa.
:``tests/test_documented_behaviour.py``: montos alternos de la cabecera y de
   la línea, y los controles de negocio (límite de líneas, existencias,
   estado de facturación) que no tenían cobertura previa.
:``tests/test_sale_order_rate.py``: cálculo y asignación de la tasa.
:``tests/test_action_confirm.py``, ``test_pricelist.py``,
   ``test_sale_order_vat.py``, ``test_sale_order_invoice_status.py``: los
   controles de confirmación, tarifas, RIF y estado de facturación.

Ejecución::

    ./scripts/odoo-test l10n_ve_sale -d <base> --tags l10n_ve_sale

Si el módulo ya está instalado en esa base, el script usa ``-i`` y no dispara
nada: hay que cambiarlo por ``-u`` en el comando que imprime ``--dry-run``.


Créditos
========

Binaural C.A. — https://binauraldev.com/
