# Feature: extensión fiscal del panel y el debug del Kiosko

## Why

El panel de órdenes del Kiosko y el shell de Debug pasan a vivir en
`l10n_ve_pos_self_order` (ver su change `kiosk-orders-panel-to-base`), porque
listar órdenes y recuperar la factura NO son operaciones fiscales. Este módulo
debe quedarse **solo con los agregados de máquina fiscal**: el estado fiscal de
la orden y la impresión/reimpresión, enganchados por extensión sobre lo de base.

## What Changes

- **`session_orders`** se elimina de `controllers/main.py` (queda en base). Se
  conserva `write_mf_invoice_data` (persistencia del número fiscal, sí fiscal).
- **`self_order_fiscal.js`**: se quitan `createKioskInvoice` y el getter
  `kioskFiscalOrders` (ahora en base como `createKioskInvoice`/
  `kioskSessionOrders`); se conserva toda la lógica de impresión/reimpresión y
  conexión bajo demanda. El número fiscal se expone al cliente igual que antes
  (`_load_pos_self_data_fields`), así el mismo `session_orders` de base trae los
  campos `mf_*` cuando este módulo está instalado.
- **`kiosk_orders_dialog_fiscal.{js,xml}`** (nuevo): extiende `KioskOrdersDialog`
  de base (patch de componente + `t-inherit`) para añadir el estado fiscal
  (`pending_fiscal`/`complete`), los badges, la línea de estado, el detalle del
  pago verificado (Megasoft) y los botones **Imprimir / Reimprimir**.
- **`kiosk_debug_dialog_fiscal.{js,xml}`** (nuevo, reemplaza `mf_debug_dialog`):
  extiende `KioskDebugDialog` de base para añadir el badge de estado de conexión
  y los botones **Comprobar estado** / **Parear máquina fiscal**.
- Se elimina el botón flotante propio (`self_order_index_fiscal.js`): el botón lo
  aporta base y abre el shell ya extendido. `self_order_index_fiscal.xml` conserva
  solo el overlay "Espere mientras se imprime su factura".
- Se borran `kiosk_fiscal_orders_dialog.{js,xml}` y `mf_debug_dialog.{js,xml}`.
- **i18n**: `es_VE.po` reescrito con solo los strings fiscales; los genéricos
  pasan al `.po` de base. También se corrige un string español hardcodeado sin
  `_t()` en `printKioskFiscalInvoice`.

## Non-goals

- No cambia la lógica de impresión fiscal (imprimir-primero, conexión bajo
  demanda, persistencia del número): solo se reubica su UI como extensión de base.
- No añade capacidades nuevas: es una reorganización de responsabilidades entre
  base y el módulo fiscal, preservando el comportamiento observable.
