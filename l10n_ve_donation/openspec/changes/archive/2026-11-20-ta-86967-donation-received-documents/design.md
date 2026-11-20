# Design

## D1. Dirección por cuentas, no por diario
Un mismo diario aloja donaciones recibidas y otorgadas. `_is_incoming_donation()` es
verdadero si el asiento es manual (`entry`), está marcado `is_donation` y alguna línea
usa una cuenta de `company.donation_income_account_ids`. Una factura de donación usa
la misma cuenta de ingresos por el producto de donación: por eso solo `entry`.
`is_incoming_donation` es un campo calculado sin almacenar: una vista no puede llamar
al método.

## D2. El donante va en las líneas
Las otorgadas llevan la compañía en las líneas (`_check_partner_donation`,
`_fill_donation_entry_line_partner`); las recibidas llevan al donante para saber de
quién viene el ingreso. Los dos mecanismos saltan las recibidas. La validación de
donante único corre en `_post` antes de `super()` (con el asiento en borrador), de modo
que la cubren `action_post`, la publicación automática y cualquier `_post` directo: no
se escribe nada en un asiento publicado (diarios con hash). Si la cabecera y las líneas
traen contactos distintos gana la cabecera (`_get_donation_counterparty`), como en 17.

## D3. Valoración de una recepción en 19
El core (`stock_account/models/stock_move.py`, `_get_account_move_line_vals`) acredita
la cuenta de valoración de la ubicación de **origen** cuando la tiene (débito: el
inventario del producto); si no, debita la de **destino**. Una recepción de donación
sale de una ubicación de Pérdida de inventario con la cuenta de ingresos: Debe
inventario / Haber ingreso. En 17 eran `valuation_out_account_id` y
`valuation_in_account_id`; en 19 es un solo campo. Validaciones: recepción →
`location_id.valuation_account_id` en las cuentas de recibidas; entrega →
`location_dest_id.valuation_account_id` no puede estarlo.

## D4. Monto y tasa por lado bolívar
`l10n_ve_rate.compute_rate` guarda en `foreign_rate` la inversa de la tasa de la
compañía y en `foreign_inverse_rate` la tasa de la compañía. Los bolívares por unidad
de la otra moneda son `foreign_rate` con la compañía en bolívares y
`foreign_inverse_rate` con la alterna en bolívares (compañía en USD).
`_compute_donation_amounts` (puro, sin base de datos) elige y devuelve el monto en
bolívares primero.

## D5. Documentos con cuerpo común y puntos de extensión
Certificado y Recibo tienen un cuerpo común (`donation_certificate_body`,
`donation_receipt_body`) y un wrapper por modelo. Otros módulos los extienden por
herencia con los elementos que tienen id (paciente, texto legal, forma de pago).
`print_donation_certificate` / `print_donation_receipt` revisan el documento antes de
imprimir (donación, tipo de asiento o picking, dirección y estado publicado o hecho), sin
depender de la visibilidad de los botones.

## D6. Recepción inerte sin cuentas
`button_validate` y `_get_donation_receipt_config_errors` solo exigen donante y
configuración contable cuando la compañía tiene `donation_income_account_ids`. Sin cuentas
la recepción valida como en `ta-86967-donation-module-1440-port`: una compañía que no recibe donaciones no
cambia. El campo de los ajustes valida la compañía (`check_company` y dominio).

## D7. Montos de un picking
`_get_donation_picking_amounts` (Recibo de la entrega y Certificado de la recepción): el
monto es el total de TODAS las líneas (`stock.move.value`) y el equivalente es ese total por
`foreign_inverse_rate` del primer asiento de valoración publicado (estable al reimprimir) o,
sin asientos, por la tasa de la fecha del documento (`compute_rate` sin error; sin tasa se
omite). Antes se mezclaban el total de todas las líneas con el monto alterno de los
asientos, que solo existen para los productos con valoración automatizada. Las líneas se
calculan una vez por documento (`_get_donation_goods_data`).

## D8. Beneficiario de una otorgada en dinero
El contacto de la cabecera se muestra como "Beneficiary" en los asientos manuales de
donación otorgada. Las líneas siguen con la compañía: `_fill_donation_entry_line_partner`
reemplaza las que copian el contacto de la cabecera al crearse. El Recibo toma al
beneficiario de la cabecera (`_get_donation_beneficiary`).

## D9. Vocabulario en inglés
En Odoo "Receipt" es la recepción entrante, y aquí "Donation Receipt" es el documento de la
ENTREGA otorgada. Para no confundirlos, el texto fuente llama "donation reception" a la
recepción entrante (picking) y reserva "Donation Receipt" para el documento; el español ya
distingue "recepción" de "Recibo de Donación".

## D10. La dirección se deduce de las cuentas y por eso no cambian con asientos publicados
Un asiento es recibido porque una línea usa una cuenta de `donation_income_account_ids`; la
dirección no se guarda. Para que un cambio de cuentas no haga pasar un asiento publicado de
Certificado a Recibo (o al revés) sin aviso, `res.company.write` rechaza agregar o quitar una
cuenta usada por asientos de donación publicados de la compañía (los borradores y las cuentas
sin uso no bloquean). Se descartó guardar la dirección en el asiento (campo almacenado y
migración de los existentes).

## D11. Beneficiario hijo
Una línea sin contacto copia el contacto comercial de la cabecera: con un beneficiario que es un
contacto hijo (ej. un médico de un hospital) copia al padre. `_fill_donation_entry_line_partner`
reemplaza por la compañía las líneas con el contacto de la cabecera o con su contacto comercial.
Cuando llega `is_donation` en una escritura el reemplazo corre **antes** del `super().write()`:
`_check_partner_donation` corre dentro de la escritura y todavía vería el contacto copiado.

## D12. La reversión de una donación no tiene documento
Una reversión copia `is_donation` y las cuentas del asiento que anula, así que cumple
`_is_incoming_donation` y parecería una donación recibida (o una otorgada) con su propio
Certificado o Recibo, emitido sobre una anulación. `print_donation_receipt` y
`print_donation_certificate` la rechazan (`reversed_entry_id`) y los botones se ocultan con la
misma condición; los documentos son los del asiento original.

## D13. El Gestor de Donaciones tiene privilegio propio

Un grupo sin `privilege_id` solo se dibuja en modo desarrollador («Extra Rights», `odoo.debug` en
`res_user_group_ids_field.js`), y dentro del privilegio de Contabilidad es una opción más del mismo
selector: guardar la ficha con otro nivel (por ejemplo Administrador) lo quita. Se crea
`res_groups_privilege_donation` («Donaciones», categoría de Contabilidad) con ese único grupo. El
registro del grupo deja de ser `noupdate` y la migración `19.0.3.0.1` lo mueve al privilegio nuevo en
las bases ya instaladas; el administrador se agrega al instalar (`post_init_hook`), no en cada
actualización.

## D14. La marca del asiento del extracto es reversible

`_mark_donation_received_from_statement` marca el asiento cuyas líneas acreditan una cuenta de
donaciones recibidas y lo guarda en `donation_marked_from_statement`. Se reevalúa en cada cambio de
líneas (`create`/`write` de la línea y `write` del asiento con `line_ids`): la marca automática se
quita cuando el asiento deja de serlo; la que puso una persona no se toca. Un pago al donante (débito
a la cuenta de ingreso) no se marca. `_check_partner_donation` no revisa los asientos de extracto y
`_post` no pide el donante en ellos: deshacer o editar la conciliación reescribe las líneas
(`Command.clear()` más `create`) y no puede fallar por la restricción. Una sola escritura por lote
y sin `is_manually_modified`.

## D15. Reverso y paso a borrador se comprueban en el servidor

Ocultar el botón no basta: la acción de reverso está ligada a la lista de asientos y cualquier
llamada llega a `_reverse_moves` y `button_draft`. `_check_donation_entry_manager` exige el grupo
Gestor (o superusuario) para los asientos manuales de donación; el asiento de extracto sí puede
restablecerse a borrador porque la conciliación lo hace. Las facturas de donación quedan fuera
porque `action_post` crea su nota de crédito con el mismo asistente.

## D16. Entregas y recepciones se valoran aparte

El core crea un solo asiento para todos los movimientos que se validan juntos. Con `_is_donation_move`
cubriendo entregas y recepciones, `_create_account_move` llama a `super()` por separado según
`picking_type_code`, para que un asiento mixto no se tome como donación recibida.

## D17. La cuenta en especie por defecto se valida al final al guardar los Ajustes

`res.config.settings` escribe cada campo relacionado por separado y sin orden fijo: la restricción de
`res.company` (la cuenta por defecto debe estar en la lista) se aplaza con el contexto
`donation_defer_account_check` y se evalúa una vez al terminar `create` y `write`.

## D18. Causa de H12: la moneda de la nota de crédito

El core toma la moneda de una nota de crédito nueva de la lista de precios del cliente, no de la
factura que revierte. `_reverse_moves` crea la nota sin `currency_id`: con una lista en bolívares, una
factura de 100 USD se revertía con 100 Bs. Se pasa `currency_id` de la factura. El test tiene un caso
de control que demuestra la causa.

## D19. Formato del Certificado en carta con migración

El formato de papel del Certificado pasa de A4 a Letter (el Recibo sigue en media carta). El registro
es `noupdate`: la migración lo cambia solo si sigue en A4, para no pisar uno elegido a propósito.

## Alternativas descartadas
- Valor unitario de la mercancía recibida (valor documentado): es una decisión de Contabilidad (C6) y
  una mejora de Producto; se probó una versión opcional y se retiró del desarrollo.
- Grupo Gestor sin privilegio (casilla independiente): solo se ve en modo desarrollador.
- Ocultar solo los botones de reverso y borrador: la acción de la lista y las llamadas RPC los alcanzan.
- Quitar la marca del extracto solo desde `create` de la línea: deshacer la conciliación reescribe las
  líneas desde el asiento.
- Campo explícito de dirección en el asiento: el usuario eligió mantener la inferencia
  por cuentas, como en 17.
- Módulo nuevo `l10n_ve_donation_received`: el usuario eligió el módulo existente.
- Contacto real en las líneas de las otorgadas: se mantiene lo de `ta-86967-donation-module-1440-port`.
