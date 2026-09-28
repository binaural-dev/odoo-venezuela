# Feature: recuperación de órdenes del Kiosko con factura rechazada

## Why

Hoy, cuando el pago del Kiosko se aprueba, el registro de la orden en Odoo
factura de forma **atómica** dentro de la misma transacción HTTP: el controlador
del core `pos_self_order` (`process_order`) crea/actualiza la `pos.order` y la
finalización (`order._process_saved_order(False)`, invocada por
`_payment_request_from_kiosk` en el flujo Megasoft) marca pagada **y** genera la
factura contable (`account.move`) — todo en el mismo cursor.

Consecuencia: **si la creación de la factura se rechaza** (secuencia SENIAT,
diario, impuesto, dato fiscal del partner, cualquier `ValidationError` de
`account.move`), la excepción propaga y **toda la transacción hace rollback** —
no queda ni la orden ni el pago en Odoo. Pero la tarjeta **ya se cobró** (la
aprobación del VPOS es client-side, `codRespuesta === "00"`). Resultado: el
cliente pagó y en Odoo no existe nada; solo queda una entrada en la cola local
`failed` de IndexedDB (`kiosk_sync_queue.js`) que, al reintentar, **vuelve a
fallar por la misma causa** y no se resuelve sola.

Este es el hueco que `l10n_ve_pos_self_order` debe cerrar, porque es este módulo
—no el de la máquina fiscal— el que gobierna el ciclo de vida de la orden del
Kiosko: aquí se fuerza `to_invoice=True` (`_check_pos_order`), se mantienen los
totales foráneos (`recompute_prices`) y vive la cola de reintento del registro.

Segundo hueco, relacionado: la respuesta JSON del VPOS de Megasoft —que trae la
prueba del cobro: `numeroAutorizacion`, `numeroReferencia`, `numeroLote`,
`numeroTarjeta`, `nombreAutorizador`, `tipoTarjeta`, `nombreVoucher`, `tid`,
`codRespuesta`— **se descarta** tras comprobar `codRespuesta === "00"`. Ni la
caja (`binaural_megasoft`) ni el Kiosko la persisten: en la caja el
`payment_status="done"` que "bloquea" la línea de pago es una propiedad
**runtime** del frontend, no un campo en BD. Así que hoy, cuando una orden queda
a medio facturar, **no hay ninguna huella durable** de qué método verificó el
cobro ni con qué referencia/autorización, justo cuando más se necesita para
conciliar.

## What Changes

Regla nueva, innegociable: **si el pago se aprobó, la ORDEN se crea siempre.** La
facturación (contable y, por extensión, fiscal) pasa a ser un paso **diferido y
reintentable**, nunca un motivo para perder la orden y el cobro.

### 1. Orden resiliente al fallo de facturación — en el seam de `l10n_ve_pos_self_order`

En vez de tocar el `_payment_request_from_kiosk` de Megasoft, la resiliencia se
implementa **una sola vez** en el punto donde el Kiosko factura, overrideando el
seam de facturación de `pos.order` en ESTE módulo (el que ya fuerza `to_invoice`
en el Kiosko), **gateado a `self_ordering_mode == 'kiosk'**:

- El tramo "pagar" (marcar pagada + picking + costo) permanece en la transacción
  principal: es un registro de venta plano, siempre debe persistir.
- La **generación de la factura** se envuelve en `with self.env.cr.savepoint():`.
  Si lanza, se captura, se registra en el log, y la orden queda **pendiente de
  facturar**: `state='paid'`, `to_invoice=True`, `account_move=False`. El
  savepoint revierte SOLO la factura; la orden + el pago sobreviven y se
  commitean al cerrar el request.

Ventaja de hacerlo aquí y no en Megasoft: es **agnóstico al método de pago**
(cubre Megasoft y cualquier terminal futuro del Kiosko), y Megasoft no cambia su
lógica de facturación — sigue llamando a `_process_saved_order` tal cual.

Efecto colateral positivo: el RPC de registro **deja de lanzar** por rechazos de
facturación (el error de negocio más común), así que la cola `failed` de
IndexedDB se reduce a rechazos verdaderamente fatales del registro completo
(token inválido, payload corrupto). El caso "factura rechazada" ya no vive en la
cola del cliente sino como estado **pendiente-de-facturar** en el servidor.

### 2. Estado "pendiente de facturar" consultable + facturación diferida

- El estado se deriva del estado nativo (`state='paid'` + `to_invoice=True` +
  `account_move` vacío) — sin inventar un campo de estado nuevo; a lo sumo un
  `computed store=False` para el dominio de las vistas.
- **Endpoint público genérico** del Kiosko (`controllers/orders.py`, junto a los
  de identificación) para **crear la factura** de una orden pendiente: valida
  `access_token` (`_verify_pos_config`) + que la orden sea de la caja, es
  idempotente (si ya tiene `account_move`, no re-factura) y devuelve el resultado.
  Es genérico (no fiscal): el panel del MF y el menú de backend lo comparten.
- **Menú de backend** que lista las órdenes de Kiosko pendientes de facturar para
  que contabilidad las vea y resuelva desde el ERP (vía autoritativa cuando la
  causa es de configuración fiscal).

### 3. Persistir la verificación de pago Megasoft *(impacto: `binaural_megasoft_self_order`)*

- `payment_page.js` deja de descartar el JSON del VPOS: lo pasa como argumento del
  RPC de registro (`megasoft_result`).
- Campos nuevos en `pos.payment` (raw JSON + subconjunto: autorización, referencia,
  lote, tarjeta enmascarada, banco/autorizador, tipo de tarjeta, código de
  respuesta), estampados al registrar el pago. Es la **prueba durable** del cobro.
- Se exponen al cliente del Kiosko vía `pos.payment._load_pos_self_data_fields`.

### 4. Fiscal y panel de recuperación *(impacto: `l10n_ve_pos_mf_self_order`)*

- `SelfOrder.confirmationPage` (`self_order_fiscal.js`): **no** auto-imprimir la
  factura fiscal cuando la factura contable está pendiente (`!order.account_move`);
  la orden queda **pendiente por facturar en máquina fiscal** también. Ambas se
  resuelven juntas desde el panel: crear factura → imprimir fiscal.
- Extender `kiosk_fiscal_orders_dialog`: estado de tres niveles (_pendiente
  factura backend_ · _pendiente fiscal_ · _completa_), sección de **pago
  verificado** (datos Megasoft persistidos), y acción por estado ("Crear
  factura" → "Imprimir factura fiscal" → "Reimprimir copia").
- La recuperación se abre desde el **menú de Debug MF** (`?debug=1`) → "Órdenes
  fiscales": es una tarea de operador/soporte, no de cara al cliente. No se añade
  un botón visible en el Kiosko normal. La vía autoritativa para contabilidad es
  el menú de backend (abajo).

## Capabilities

### New Capabilities

- `pos-self-order-kiosk-invoice-recovery`: cuando el pago del Kiosko se aprueba,
  la orden se crea siempre; la facturación contable y fiscal son pasos diferidos
  y reintentables; la verificación de pago Megasoft se persiste como prueba
  durable; y las órdenes a medio facturar se recuperan desde un panel del Kiosko
  (fuera de debug) y desde un menú de backend.

## Impact

- **Módulo dueño — `l10n_ve_pos_self_order`:** override del seam de facturación
  (savepoint, gateado a kiosko), estado pendiente derivado + `computed` opcional,
  endpoint público genérico de facturación diferida, menú de backend, y ajuste
  documental de la cola `kiosk_sync_queue.js` (nuevo reparto pendiente-servidor
  vs failed-cliente).
- **Impacto — `binaural_megasoft_self_order`:** campos `megasoft_*` en
  `pos.payment`, captura del JSON en `payment_page.js`, exposición vía
  `_load_pos_self_data_fields`. NO cambia su lógica de facturación (la resiliencia
  la aporta el seam de self_order).
- **Impacto — `l10n_ve_pos_mf_self_order`:** guarda `account_move` en el
  auto-print de `confirmationPage`, extensión del panel de órdenes fiscales
  (estado + pago verificado + botón "Crear factura" que llama al endpoint de
  self_order), punto de entrada visible.
- **No se toca** `binaural_megasoft` (la caja): la persistencia del JSON se hace
  en el módulo puente del Kiosko. Promoverla a la caja queda como mejora futura.
- **No se toca** `l10n_ve_mf_base` (driver) ni el `PosStore`/builder fiscal de la
  caja.
- **Riesgo:** medio-bajo. El punto delicado es el savepoint alrededor de la
  facturación: hay que identificar el seam exacto donde el Kiosko genera la
  factura en Odoo 19 (`_process_saved_order` → método de facturación) para
  envolver SOLO eso, dejando intactos paid/picking/costo. Se cubre con tests
  server-side (ver `tasks.md` §7).
- **Precondición:** el Kiosko ya identifica al cliente por cédula
  ([[l10n-ve-self-order-kiosk-identification]]) y factura por defecto
  ([[l10n-ve-pos-self-order-kiosk-invoicing]]); la impresión fiscal existe
  ([[l10n-ve-pos-mf-self-order-fiscal-print]], cuyo auto-print se refina aquí).
- **Fuera de alcance:**
  - Reintento automático server-side (cron) de la facturación pendiente: v1 es
    manual (panel del Kiosko + menú de backend). Un cron es mejora futura.
  - Persistir el JSON del VPOS también en la caja (`binaural_megasoft`).
  - Editar/desbloquear la línea de pago aprobada en la caja (el
    `payment_status="done"` sigue igual; aquí no se toca la caja).

References: Tarea 78767 (Autopago POS V19),
https://binaural.odoo.com/odoo/action-341/78767
