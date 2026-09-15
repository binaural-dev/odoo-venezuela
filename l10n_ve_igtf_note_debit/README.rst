===========================================
Venezuela - IGTF Nota de Débito Automática
===========================================

.. |badge1| image:: https://img.shields.io/badge/licence-LGPL--3-blue.png
    :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
    :alt: License: LGPL-3

|badge1|

Este módulo agrega un flujo **alterno y opcional** de percepción de IGTF sobre el
que ya provee ``l10n_ve_igtf``: en vez de contabilizar el IGTF como una línea
dentro del mismo asiento de pago/anticipo (flujo histórico, "inline"), genera
un documento fiscal independiente -- una **Nota de Débito** (vía
``account_debit_note``) -- vinculada a la factura de origen, con su propio
número de control (Forma Libre), conforme a las Providencias SENIAT 0071/0102.

Es 100% opt-in por compañía. Mientras el "Modo de Percepción de IGTF"
(``igtf_note_debit_mode``) esté en "Línea en el mismo asiento", este módulo
no cambia absolutamente nada del comportamiento existente.

**Tabla de Contenidos**

.. contents::
   :local:

Configuración
=============

En **Ajustes Binaural > Contabilidad > IGTF**:

* **Modo de Percepción de IGTF**: ``inline`` (comportamiento histórico) o
  ``debit_note`` (nuevo flujo, el que agrega este módulo).
* **Producto de Percepción de IGTF**: producto de tipo Servicio usado como
  única línea de la ND. Debe tener asignado el impuesto Exento/No Sujeto de
  venta y compra (IGTF no es base de IVA, pero ``l10n_ve_accountant`` exige
  que todo producto tenga exactamente un impuesto de venta y uno de compra).
* **Incluir IGTF en el pago por defecto**: valor por defecto del check
  homónimo en el wizard de registro de pago (ver más abajo). El usuario
  puede cambiarlo en cada pago puntual.
* **Diario VEF para cobro de IGTF**: diario en Bolívares usado para el pago
  aparte del IGTF, cuando corresponde (ver "Cobro del IGTF" más abajo).

Funcionamiento
==============

1. Registro de pago (factura directa, no anticipo)
---------------------------------------------------

Al registrar un pago en divisas desde el wizard estándar
(**Registrar Pago**), si el pago aplica IGTF y el modo es ``debit_note``:

* El wizard muestra el check **"Incluir IGTF en el pago"** (por defecto,
  el valor configurado en la compañía).
* Si se calcula un IGTF y no se incluye en el pago, el wizard muestra un
  aviso con el desglose **Importe + IGTF = Total a pagar**, para que quede
  claro que hay que transferir/entregar ese monto total, aunque el pago que
  se registra en el sistema solo cubra la factura.
* Al confirmar, se genera automáticamente la Nota de Débito por el monto
  exacto de IGTF (``prepare_igtf_payment_debit_note``), vinculada a la
  factura y al pago de origen.

2. Cobro del IGTF (cómo se salda la ND)
----------------------------------------

Según el check "Incluir IGTF en el pago":

* **Marcado**: el pago ya cubre factura + IGTF juntos -- el residual
  sobrante del propio pago se concilia directo contra la ND
  (``settle_igtf_debit_note`` → ``js_assign_outstanding_line``).
* **Desmarcado**: el pago solo cubrió la factura -- se crea automáticamente
  un ``account.payment`` aparte, siempre en VEF (Bolívares), por el monto
  exacto de la ND, y se concilia contra ella
  (``_settle_igtf_debit_note_with_vef_payment``).

3. Anticipos (cruce de anticipo contra factura)
-------------------------------------------------

Cuando el pago es un anticipo y se cruza contra una factura (desde el
widget de "líneas salientes"), ``_create_advance_payment_move`` se
sobrescribe para el modo ``debit_note``: arma el asiento de cruce **sin**
la línea embebida de IGTF, calcula el IGTF correspondiente a la porción
aplicada y genera/concilia la ND por separado.

4. Conciliación manual de un pago directo (no anticipo)
----------------------------------------------------------

Si en vez de usar el wizard de registro de pago se asigna manualmente un
pago existente a una factura (widget de "líneas salientes" de la factura,
``js_assign_outstanding_line``), y ese pago no es un anticipo pero sí aplica
IGTF, el módulo:

* Calcula cuánto del pago corresponde a la factura y cuánto al IGTF (el
  monto de IGTF **nunca** se concilia contra la factura -- solo la porción
  base), usando una conciliación parcial (``account.partial.reconcile``)
  para separar ambas porciones sin necesidad de un asiento intermedio.
* Soporta pago y factura en monedas distintas (ej. pago en USD, factura en
  VEF): el IGTF siempre se calcula/expresa en la moneda de compañía y se
  convierte a cada lado según corresponda, evitando el error de redondeo
  típico de convertir un monto ya truncado.
* Genera la ND por el remanente y la concilia igual que en los otros casos.

5. Base imponible de IGTF en la factura (reportes/UI)
--------------------------------------------------------

``compute_bi_igtf`` se sobrescribe para que los campos que ve el usuario en
la factura reconozcan tanto la línea embebida (modo ``inline``) como la ND
independiente (modo ``debit_note``) -- sin esto, una factura pagada con ND
de IGTF los mostraría en cero:

* ``bi_igtf``: base imponible del IGTF, en moneda de compañía. No se
  re-convierte a la tasa del pago -- toma el monto ya asentado por la
  conciliación, que refleja la tasa con la que la factura quedó
  contabilizada.
* ``foreign_bi_igtf``: la misma base, expresada en la moneda de la factura.
* ``alter_bi_igtf`` ("IGTF Apply"): el monto de IGTF efectivamente cobrado
  -- coincide con el total de la ND.
* ``igtf_top_aply``: el tope de IGTF (base × alícuota configurada en la
  compañía).

El diferencial cambiario entre la tasa de la factura y la tasa del pago es
responsabilidad exclusiva de ``l10n_ve_exchange_difference`` (módulo
hermano, si está instalado) -- este módulo nunca lo calcula ni lo corrige
en ``bi_igtf``.

6. Reversión (desconciliar/cancelar un pago con ND)
-------------------------------------------------------

Si el pago que originó una ND se desconcilia o cancela
(``js_remove_outstanding_partial`` → ``remove_igtf_from_account_move``,
incluye el caso de cancelar el pago directamente con "Fijar a Borrador" y
luego "Cancelar", sin pasar por el widget), se genera automáticamente una
**Nota de Crédito en Forma Libre** que reversa la ND
(``create_note_credit_igtf``), en vez de intentar "desarmar" una línea
embebida que en este flujo no existe. Soporta tanto ventas (``out_invoice``)
como compras (``in_invoice``).

7. Tasa de cambio usada para el cálculo (``indexed_default``)
------------------------------------------------------------------

El campo ``indexed_default`` (de ``l10n_ve_accountant``, ligado a
``company.indexaxion_payment_mode``) determina qué tasa de cambio se usa
para calcular el IGTF:

* **Activado** (comportamiento por defecto): se usa la tasa de cambio del
  día del **pago**.
* **Desactivado**: se usa la tasa de cambio del día de la **factura**.

Esto afecta tanto el monto de IGTF que calcula la base (``l10n_ve_igtf``)
como la conversión a moneda de compañía que hace este módulo para armar la
ND (``wizard/account_payment_register.py::_create_payments``) -- ambos
pasos deben usar la MISMA fecha de conversión, o se reintroduce la tasa
"equivocada" en un paso aunque el otro ya sea correcto.

8. Bloqueo de pagos agrupados multi-factura
------------------------------------------------

Con el modo ``debit_note`` activo, "Agrupar Pagos" (``group_payment``) no se
puede usar cuando el pago cubre más de una factura por un diario IGTF: cada
factura pagada con IGTF debe generar su propia ND -- un solo pago agrupado
no puede repartirse limpiamente entre varias ND. El wizard bloquea la
acción con un error explícito (``_check_igtf_note_debit_group_payment``),
pidiendo desmarcar "Agrupar Pagos" y registrar cada factura por separado.

Indicadores
===========

* La factura expone ``has_pending_igtf_debit_note``: True si tiene una ND
  de IGTF posteada y pendiente de cobro -- útil para mostrar un aviso en la
  vista sin depender de ``payment_state`` (la factura puede figurar
  "Pagada" aunque su ND de IGTF siga sin cobrar, ya que son documentos
  contables independientes).

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
