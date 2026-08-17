# Feature: impresión en máquina fiscal en el Kiosko (l10n_ve_pos_mf_self_order)

## Why

En la caja normal, `l10n_ve_pos_mf` imprime la factura en la máquina fiscal
(TFHKA, Web Serial) **client-side**: al Validar el pago,
`OrderPaymentValidation.finalizeValidation` llama `PosStore.pushToMF(order)`,
que arma el payload desde la orden en memoria (`get_data_invoice` +
`_convertOrderForDriver`) y se lo manda al driver `window.fiscalPrinter`
(`TfhkaDriver` de `l10n_ve_mf_base`). El servidor solo persiste el número fiscal
devuelto (`mf_invoice_number`) y lo estampa en el `account.move`
(`_prepare_invoice_vals`).

El Kiosko/Autopedido (`pos_self_order`) carga un bundle **distinto**
(`pos_self_order.assets`) que no incluye nada de eso. Hoy la orden del Kiosko se
factura en el servidor (ver [[pos-self-order-kiosk-invoicing]]) pero **no se
imprime en la máquina fiscal**.

Además, el Kiosko es **online-first por diseño**: en modo kiosko
`pos_self_order` desactiva IndexedDB y toda la cola local
(`data_service.js:initIndexedDB` y compañía son no-op salvo en modo `mobile`), y
manda cada orden al servidor por un RPC bloqueante. Si el servidor Odoo no está
accesible (despliegues con Odoo remoto), una orden ya **pagada** puede quedarse
"a medio camino": el pago se aprobó (la tarjeta ya se cobró en el VPOS) pero la
factura no se imprime y la orden no se registra.

El objetivo de esta característica es: **una vez el pago está aprobado y la orden
confirmada y REGISTRADA en Odoo, se imprime la factura fiscal en local.** La
impresión fiscal (Web Serial → TFHKA) ya es 100% local; lo que falta es (a)
traerla al bundle del Kiosko reutilizando el driver y la lógica de
`l10n_ve_pos_mf`, y (b) dispararla en el momento correcto.

## What Changes

### Principio: REGISTRAR-PRIMERO, imprimir-después

Regla fiscal innegociable: **una factura fiscal (número SENIAT) nunca debe
existir sin su orden/factura en Odoo.** Por eso el Kiosko REGISTRA primero y
imprime después:

1. Al aprobarse el pago, se **registra** la orden en Odoo (RPC `/kiosk/payment`),
   que crea la `pos.order` + la factura contable (`account.move`).
2. Solo cuando la orden ya existe en Odoo (al llegar a la **confirmación**) se
   **imprime** la factura fiscal en la máquina, y el número resultante se
   **persiste** en la orden y en el `account.move` vía
   `pos.order.write_mf_invoice_data` (el MISMO método que usa la caja en
   `PrintPendingOrderButton`), a través de un endpoint público del Kiosko.
3. Si la impresión falla, la orden queda **pendiente de imprimir** (registrada y
   facturada, sin número fiscal) y se reimprime luego (menú Debug MF / respaldo
   caja) — la numeración fiscal no tiene huecos: la máquina numera solo lo que
   imprime.
4. Si el REGISTRO falla (servidor caído), NO se imprime (no hay orden en Odoo);
   la orden se **encola** para reintento automático y la impresión queda
   pendiente hasta que el registro entre.

Se distinguen dos "facturas": la **fiscal** (impreso legal de la TFHKA →
inmediata, local) y la **contable de Odoo** (`account.move` → diferida, al
sincronizar).

### Módulo puente nuevo `l10n_ve_pos_mf_self_order`

`auto_install=True` cuando estén `l10n_ve_pos_mf` + `l10n_ve_pos_self_order`.
Mantiene `l10n_ve_pos_self_order` independiente de la máquina fiscal (hay
despliegues sin MF). Mismo patrón que `binaural_megasoft_self_order`.

#### Backend — exponer datos fiscales al cliente del Kiosko

El Kiosko usa loaders con lista EXPLÍCITA de campos (`_load_pos_self_data_fields`),
distintos del loader de caja (`_load_pos_data_fields`) donde `l10n_ve_pos_mf` ya
inyecta los campos fiscales. Se replican para el Kiosko:

- `pos.config`: `serial_machine`, `flag_21`, `traditional_line`, `has_cashbox`,
  `access_button_mf`, `message_in_head`, `enable_auto_sync`,
  `auto_sync_interval`, `mf_skip_invoice_pdf`, `receipt_header`, `receipt_footer`.
- `pos.payment.method`: `code_fiscal_printer`.
- `account.tax`: `fiscal_code`.
- `pos.order`: `mf_invoice_number`, `fiscal_machine`, `mf_reportz` (para que el
  número fiscal viaje al servidor en `serializeForORM` y vuelva en el read).

#### Frontend — driver, payload y enganche (`pos_self_order.assets`)

- **Driver reutilizado tal cual**: se cargan `l10n_ve_mf_base/static/src/{core,
  drivers}/*.js` en el bundle del Kiosko (autocontenidos, solo dependen de
  `navigator.serial`). Singleton global `window.fiscalPrinter` compartido con la
  caja si conviven en el mismo navegador.
- **Builder propio del Kiosko (NO se toca `PosStore`)**: el Kiosko arma su
  propio payload fiscal en el módulo nuevo, sin extraer ni modificar el builder
  de la caja. Se justifica porque el Kiosko es un subconjunto mucho más simple:
  solo `out_invoice` (sin notas de crédito), **sin descuento global**, **sin
  cajero**, con las líneas de pago pasadas explícitas. Toda la complejidad de
  `get_data_invoice`/`_convertOrderForDriver` (NC, descuento global estrategia A,
  recuperación de factura afectada) el Kiosko no la usa, así que el builder queda
  en ~60-80 líneas autocontenidas que producen la MISMA forma de payload que
  espera el driver. El precio foráneo se calcula desde `order.foreign_currency_
  rate` (que `recompute_prices` ya fija). Trade-off aceptado: la forma del payload
  del driver queda en dos sitios (caja + Kiosko), pero es el contrato estable de
  la TFHKA; a cambio, **cero riesgo para el `PosStore` de producción de la caja**.
- **Conexión al puerto**: auto-conexión silenciosa al arrancar (kiosko
  desatendido, sin botón de cara al cliente) + pareo manual desde el menú Debug.
- **Enganche registrar-primero (genérico)**: la impresión se dispara en
  `SelfOrder.confirmationPage()` — el punto por el que pasan TODOS los pagos
  (Megasoft/terminal → bus `PAYMENT_STATUS` → `connectNewData` → confirmación),
  cuando la orden YA está registrada y facturada en Odoo (con id de servidor). Se
  imprime solo si la orden está pagada y sin `mf_invoice_number`; el pago se
  deriva de `order.payment_ids`. **Megasoft NO imprime** (solo registra +
  encola); toda la lógica fiscal vive en este módulo.
- **Persistencia del número (reuso de `write_mf_invoice_data`)**: tras imprimir,
  el número se persiste en la orden y el `account.move` con el MISMO método
  server que la caja (`pos.order.write_mf_invoice_data`), expuesto al Kiosko
  público por un endpoint dedicado (`controllers/main.py` →
  `/l10n_ve_pos_mf_self_order/kiosk/write_mf_invoice_data`, valida `access_token`
  y que la orden pertenezca a la caja).
- **Persistencia + reintento reutilizando el motor del POS**: la orden pendiente
  se guarda en **IndexedDB** reutilizando el `PosData` que el Kiosko ya carga
  pero tiene desactivado en modo kiosko (`data_service.js` — no-op salvo
  `mobile`). Se reactiva IndexedDB **solo para las órdenes pendientes** (no para
  cachear el dataset del servidor, que el Kiosko apaga a propósito por ser
  desatendido), y se replica el patrón de cola/reintento del POS
  (`network.unsyncData` + `syncData()`, que reintenta y conserva la operación al
  fallar). **Muro arquitectónico:** el `syncData`/`execute` del POS sincroniza
  vía `call_kw` autenticado (`sync_from_ui`), inaccesible desde el Kiosko
  (frontend público con `access_token`); por eso el disparo de sincronización va
  por el **RPC público del Kiosko** (`/pos-self-order/process-order` /
  `/kiosk/payment`), no por `sync_from_ui`. Se reutiliza la mitad de
  almacenamiento (IndexedDB), no el loop autenticado.

#### Reimpresión de facturas fiscales fallidas (modo debug)

Cuando una impresión fiscal falla, se persiste el payload ya armado en local
(marcado "pendiente de imprimir") y se expone una acción —gated por **modo
debug**— para **reenviar** esa factura a la impresora fiscal, sin volver a
cobrar. Reutiliza el mismo driver (`printInvoice(payload)`).

## Capabilities

### New Capabilities

- `pos-self-order-kiosk-fiscal-print`: el Kiosko imprime la factura fiscal
  (TFHKA, Web Serial) al confirmar la orden, en local, bajo el modelo
  registrar-primero (la orden ya existe en Odoo antes de imprimir), persistiendo
  el número con `write_mf_invoice_data`, y con reimpresión de fallidas por modo
  debug + cola de reintento del registro ante servidor caído.

## Impact

- **Módulos**: `l10n_ve_pos_mf_self_order` (NUEVO — todo el frontend del Kiosko
  y el backend de exposición de datos), y el enganche en el flujo de finalización
  del Kiosko (Megasoft en `binaural_megasoft_self_order`, pago-en-caja en el
  propio módulo nuevo).
- **NO se toca `PosStore` de la caja** (`l10n_ve_pos_mf`): el Kiosko lleva su
  propio builder; el único reuso verbatim es el driver (`l10n_ve_mf_base`, que no
  se modifica, solo se inyecta en el bundle del Kiosko).
- **No toca** el core `pos_self_order` ni `point_of_sale` (solo overrides).
- **Depende de** que la orden llegue con `partner_id` identificado
  ([[l10n-ve-self-order-kiosk-identification]]) y con totales foráneos
  ([[l10n-ve-pos-self-order-kiosk-invoicing]]).
- **Riesgo**: bajo — todo el cambio es aditivo (módulo nuevo + bundle del
  Kiosko). No se toca el `PosStore` ni el driver de la caja. El punto a vigilar
  es reactivar IndexedDB en el Kiosko sin arrastrar el caché de datos del
  servidor que el core apaga a propósito (ver `tasks.md` 5.3).
- **Precondición operacional**: la máquina fiscal debe estar conectada por
  USB/serial a la PC del Kiosko; la autorización inicial del puerto Web Serial
  requiere un gesto del usuario una vez (luego `autoConnect()`).
- **Fuera de alcance**:
  - Paridad offline COMPLETA del Kiosko (empezar órdenes nuevas durante un corte
    total): innecesario porque el pago con tarjeta necesita red igual. Se cubre
    solo la resiliencia del tramo confirmar → imprimir → sincronizar (Nivel A).
  - Notas de crédito / devoluciones en el Kiosko: el Kiosko no las hace.
  - Reportes X/Z desde el Kiosko: fuera de alcance.

References: Tarea 78767 (Autopago POS V19),
https://binaural.odoo.com/odoo/action-341/78767
