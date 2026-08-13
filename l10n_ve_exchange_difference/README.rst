=====================================================
Venezuela - Diferencial Cambiario como Notas de Débito/Crédito
=====================================================

.. |badge1| image:: https://img.shields.io/badge/licence-LGPL--3-blue.png
    :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
    :alt: License: LGPL-3

|badge1|

Este módulo documenta el diferencial cambiario que surge al conciliar una
factura de cliente en moneda extranjera contra un pago con una tasa de
cambio distinta, usando Notas de Débito/Crédito **fiscales reales** (con
correlativo, vinculadas a la factura de origen) en vez del asiento contable
genérico e interno que Odoo crea por defecto.

Cómo funciona
"""""""""""""

1. Al conciliar la línea de cuenta por cobrar de una factura de cliente
   contra la de un pago, se omite el asiento automático de diferencial de
   Odoo pasando la llave de contexto ``no_exchange_difference`` -- la misma
   que usa Odoo internamente para este propósito -- dejando el residual
   abierto en vez de cerrarlo con ese asiento genérico.

2. El monto exacto del diferencial **no** se calcula a partir de lo que
   quede de residual en la factura o en el pago (eso puede incluir montos
   que no tienen nada que ver con la tasa de cambio, por ejemplo si el pago
   es por un monto distinto al de la factura). Se calcula a partir del
   ``account.partial.reconcile`` que la propia conciliación acaba de crear:
   su monto realmente emparejado (``debit_amount_currency``), multiplicado
   por la diferencia entre la tasa propia de la línea de la factura y la
   del pago (``balance / amount_currency`` de cada una, fija desde que se
   creó cada línea).

3. Con ese monto se emite:

   - Una **Nota de Débito** (ganancia cambiaria) si el residual quedó del
     lado del crédito -- vinculada a la factura mediante ``debit_origin_id``.
   - Una **Nota de Crédito** (pérdida cambiaria) si el residual quedó del
     lado del débito -- vinculada a la factura mediante ``reversed_entry_id``.

   Ambas quedan además vinculadas explícitamente vía
   ``l10n_ve_exchange_invoice_id``, se postean con correlativo fiscal real
   en el diario dedicado, y se concilian de inmediato para cerrar el
   residual por completo.

4. Si la conciliación factura-pago que originó la nota se rompe
   (botón "✕" del widget de pagos), la nota **no se cancela ni se borra**
   -- ya es un documento fiscal posteado con correlativo real. En su lugar
   se revierte automáticamente (Nota de Crédito revierte una Nota de
   Débito, y viceversa), igual que hace Odoo con su propio asiento
   genérico de diferencial al desconciliar. Intentar desconciliar la
   propia nota directamente (sin pasar por la conciliación original) está
   bloqueado.

5. Este comportamiento **solo aplica a facturas y notas de crédito de
   cliente**. Cualquier otro caso (facturas de proveedor, asientos
   manuales, compañías con el modo desactivado) sigue el comportamiento
   nativo de Odoo, sin modificaciones -- incluyendo su propio asiento
   genérico de diferencial, que de todas formas queda etiquetado
   (``l10n_ve_exchange_diff_entry``) para identificarlo.

Configuración
"""""""""""""

* Compañía (``res.company``), en ``Ajustes > Contabilidad``:

  * Usar Notas de Débito/Crédito para diferencial cambiario (activable/desactivable).
  * Producto de Nota de Diferencial Cambiario (debe tener un impuesto exento configurado).

* Diario de venta (``account.journal``):

  * Secuencia dedicada para las Notas de Débito de diferencial cambiario.

Limitaciones
""""""""""""

* Solo cubre facturas/notas de crédito de **cliente** (``out_invoice``/
  ``out_refund``). Facturas de proveedor y otros documentos no se ven
  afectados por este módulo.
* Requiere el producto de diferencial cambiario configurado -- si falta,
  la conciliación falla con un error claro en vez de dejar una nota
  incompleta.

**Tabla de Contenidos**

.. contents::
   :local:

Créditos
========

Autor/es
~~~~~~~~

* Binauraldev

Mantenedor/es
~~~~~~~~~~~~~

Este módulo es mantenido por Binaural.

.. image:: https://binauraldev.com/wp-content/uploads/2022/01/logo-binaural.png
   :alt: Binaural dev
   :target: https://binauraldev.com/
