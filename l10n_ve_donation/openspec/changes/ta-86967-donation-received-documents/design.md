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
`foreign_inverse_rate` con la alterna en bolívares (compañía en USD, como Higea).
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

## Alternativas descartadas
- Campo explícito de dirección en el asiento: el usuario eligió mantener la inferencia
  por cuentas, como Higea.
- Módulo nuevo `l10n_ve_donation_received`: el usuario eligió el módulo existente.
- Contacto real en las líneas de las otorgadas: se mantiene lo de `ta-86967-donation-module-1440-port`.
