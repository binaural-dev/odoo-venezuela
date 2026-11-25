# Design

## D1. El módulo vive en odoo-venezuela, no en el repo del cliente

En las instancias 19 la raíz del cliente va **después** de `odoo-venezuela` en
`addons_path` (arreglo de traducciones), así que una carpeta
`l10n_ve_donation/` en el repo del cliente quedaría tapada. Los dependientes
(`binaural_operative`, `binaural_stock_dispatch_note`, `l10n_ve_inventory_book`)
dependen del módulo por nombre. Los clientes lo consumen desde odoo-venezuela.

## D2. `is_donation` en `stock.picking` pertenece al módulo (dependencia invertida)

En 19, `l10n_ve_donation` depende de `l10n_ve_stock_account` y toda la lógica
de donación se sacó de ahí. Lo que la lógica de #1440 puso en
`l10n_ve_stock_account` de 17 (campo guardado, `_get_new_picking_values`,
rama del motivo, `readonly` de la vista) se rehace dentro del módulo sin
tocar `l10n_ve_stock_account`. Se usa el campo de V19 (computado guardado
desde `sale_id.is_donation`, `readonly=False`): para un picking del menú el
valor llega por `default_get` con el contexto `donation_menu` (no
`default_is_donation`, que llegaría a todo registro creado desde la acción,
incluidos los asientos de valoración).

## D3. Asiento de valoración sobre la API contable de stock de 19

El core 19 no tiene capas de valoración ni `_prepare_account_move_vals`.

- El valor del movimiento está en `stock.move.value` (positivo en salidas).
- `_create_account_move` crea **un solo** `account.move` para todo el
  recordset y lo publica: se divide el recordset en movimientos de donación
  y el resto, y se llama a `super()` sobre cada subconjunto. Los asientos de
  donación se marcan después (`is_donation`, `ref`) con una escritura
  explícita: ningún `default_is_donation` entra al contexto.
- `_get_account_move_line_vals` devuelve diccionarios sin `partner_id`; el
  partner de las líneas se computa desde la cabecera (el beneficiario) y
  `_check_partner_donation` rechazaría esas líneas. Se fuerza el partner de la
  compañía en cada línea y se agrega el motivo al nombre.
- La ubicación tiene una sola cuenta, `valuation_account_id`
  (`valuation_in_account_id` de 17 desaparece). La entrega debita la cuenta
  de la ubicación de destino (`usage = inventory`) y acredita la de
  valoración del producto.
- `product.type == 'product'` pasa a `product.is_storable`.

Solo aplica a `is_donation and not sale_id and outgoing`; las entregas de un
pedido de donación siguen el flujo normal de venta.

## D4. Motivo de traslado 'Donación' por defecto, no forzado

La base 19 (`_compute_allowed_reason_ids`) reescribe todo motivo que no esté
en la lista de permitidos, y 'Donación' no figura en ella. Se **agrega** a la
lista (no se sustituye) para las salidas de donación y se asigna al marcar
`is_donation`; la vista lo deja en solo lectura. También se asigna en
`create`/`write` porque, cuando el motivo llega en los valores (la base da a
cada picking nuevo el motivo por defecto de su tipo de operación), el
cómputo de los permitidos no puede sobrescribirlo. El libro de inventario
clasifica por `transfer_reason_id.code`: `donation` va a la columna de
donación y `self_consumption` a autoconsumo.

## D5. La NC de donación sigue el flujo del wizard de alerta

`l10n_ve_accountant.action_post` devuelve el wizard `move.action.post.alert.wizard`
y no publica; el wizard llama otra vez con `move_action_post_alert=True`.
`action_post` de donación conserva la guarda de la versión 17: si el padre devolvió un
dict, retorna sin hacer nada; en la segunda llamada reversa y publica la nota
de cada factura que **esa llamada** publicó (se calcula la lista de borradores
antes de `super()`), de modo que un lote de varias facturas recibe una nota
cada una y volver a publicar una ya publicada no la reversa otra vez. Como esa
publicación ocurre sin la clave de contexto de `_reverse_moves`, la exención de
la validación de origen de `l10n_ve_invoice` se decide por el campo guardado
`is_donation` (`_l10n_ve_skip_refund_origin_validation`). Se corrige respecto a
la versión 17 el uso de `self` en lugar de `move` (`active_ids`, `journal_id`).

La nota de crédito se crea **sin** `skip_invoice_sync`. En 19 la llave impide al core generar las líneas de
impuesto y de cobro: la nota quedaba en 0,00 y la factura sin neutralizar.
En 17 ya se había quitado por un desbalance parecido (tarea 69610). Se descubrió al recorrer el flujo en la
interfaz: ningún test comprobaba los montos de la nota.

## D6. Costo del certificado de entrega

`unit_cost = abs(move.value / move._get_valued_qty())` y
`total = unit_cost * line.quantity_product_uom`, de modo que la reimpresión
da siempre el mismo número (no depende de `standard_price`). Antes de validar
el costo es 0.

## D7. Vistas y seguridad de 19

`<list>` en lugar de `<tree>`; `type` en lugar de `detailed_type`; ajuste de
configuración anclado a `l10n_ve_base.l10n_ve_base_view_res_config_settings`
bajo `block[@name='l10n_ve_stock_block']` con el mismo `div id`
(`binaural_stock_dispatch_note` lo usa); grupo con `privilege_id` y
`user_ids`.

## D8. Asiento manual de donación: partner en borrador, nada al publicar

Las donaciones recibidas en dinero son asientos manuales que el usuario marca
(flujo F3 del manual de donaciones de la versión 17). Se restaura la vista de la versión 17:
`is_donation` visible y editable solo en asientos manuales en borrador (V19 lo
ocultaba hasta estar marcado).

El partner de la compañía en los apuntes ya no se escribe en `action_post`: un
diario con "Bloquear asientos con hash" no permite editar partner ni etiqueta de
un asiento publicado y la publicación fallaba. Se asigna en borrador, en tres
puntos: el `create` de `account.move.line` (el cliente web manda
`partner_id: False`, y un valor en los valores de creación no se calcula, por lo
que un `_compute_partner_id` no sirve), el `write` de `account.move` al marcar
`is_donation`, y justo antes de publicar. Los apuntes que ya tienen partner se
respetan y el constraint `_check_partner_donation` sigue validando.

Se retira el sufijo `" - <ref>"` que se agregaba a la etiqueta de los apuntes: venía de la
versión 17 y solo lo consume el módulo propio de un cliente en 17 (que lo quita para armar el
concepto del recibo).

## D9. "Crear factura" oculto en una donación sin pedido

`show_create_invoice` se apaga con un override de `_compute_button_visibility`
para `is_donation and not sale_id`: facturarla emitiría una factura fiscal
normal al beneficiario, sin marca de donación ni nota de crédito (#1440 no
factura esas donaciones).

## D10. Alternativas descartadas

- **Dejar el módulo V19 y parchearlo**: dos caminos para la misma donación.
- **Forzar el partner de la compañía en la cabecera** (V19): la cabecera debe
  registrar al donante o beneficiario real (certificado).
- **Mantener el sufijo moviéndolo a antes de publicar**: se descartó por
  decisión del usuario; solo el módulo propio de un cliente lo usaba y tolera su ausencia.
- **Calcular el partner de los apuntes en `_compute_partner_id`**: no se
  ejecuta cuando el cliente envía `partner_id: False`.
- **Forzar el motivo 'Autoconsumo'** (V19): 'Donación' por defecto, solo
  lectura (el libro de inventario clasifica por el código del motivo).

## Dependencias y manifest

`stock_account` en `depends` (campo `account_stock_journal_id` core: no se
redefine); `auto_install: False`; versión `19.0.3.0.0`. Contrato público que
usan los módulos de cliente (no se renombra): `print_donation_certificate`,
`_get_donation_delivery_config_errors`, `_get_donation_product_lines`,
`_get_donation_grand_total`, `product_line_donation`,
`is_donation_picking_type`, `donation_reason`, `donation_menu`.

> Nota (change `ta-86967-donation-received-documents`): `print_donation_certificate` cambió
> de significado. Ya no imprime el documento de la entrega (ahora `print_donation_receipt`,
> el Recibo) sino el Certificado de una donación RECIBIDA. Los módulos de cliente
> en 17 usan los nombres con el significado de 17; al portarlos a 19 se ajustan a este contrato.

## Testing

`TransactionCase` sobre `StockAccountTestCommon` de `l10n_ve_stock_account`.
Fixtures en `tests/common.py` (almacén de donación, ubicación `inventory` con
cuenta de valoración, tipo de operación de salida, producto con valoración
`real_time`). Comando en `STATE.md`.
