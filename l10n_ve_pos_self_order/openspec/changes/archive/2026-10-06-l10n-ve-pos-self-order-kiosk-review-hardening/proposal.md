# Feature: endurecimiento de seguridad y correctitud del Kiosko (revisión PR #1161)

## Why

La revisión del PR #1161 (adaptación del Kiosko/Autopedido a la localización VE)
encontró un bloque de hallazgos que conviene resolver antes de dar por cerrado el
Kiosko en producción. La raíz de la mayoría es una: los módulos exponen **6 rutas
`auth="public"`** gateadas **solo** por el `access_token` de `pos.config` —un
token a nivel de **dispositivo**, embebido en la URL/QR del Kiosko y visible para
cualquiera frente a la pantalla; no es un secreto por-usuario— y encima cada ruta
hace `.sudo()`.

Eso desactiva las dos defensas que el core `pos_self_order` aplica a propósito
(verificado contra Community 19.0, `addons/pos_self_order/controllers/orders.py`):

1. `_verify_pos_config` devuelve un env con **privilegio reducido**
   (`sudo(False)` + usuario/compañía de la caja) para que ACLs y record rules
   sigan filtrando en rutas públicas. El `.sudo()` del PR lo anula.
2. Toda acción sobre una **orden concreta** exige el **token por-orden** vía
   `consteq()` (`remove_order`, `get_orders_by_access_token`). El PR valida solo
   `config_id`.

Consecuencia: fuga de PII (cédula/RIF de toda la clientela), enumeración de
cédulas, y manipulación de datos fiscales/facturación sobre órdenes ajenas. A
esto se suman dos temas de **correctitud fiscal** y una **brecha de cobertura**
en las features centrales del PR.

Esto choca además con la política de datos de la empresa (la información no debe
salir de la empresa).

## What Changes

### 1. Control de acceso de las rutas públicas del Kiosko (bloqueante)

Alinear las 6 rutas con el modelo del core: **token por-orden** para toda acción
sobre una orden concreta, y **quitar el `.sudo()` general** (operar con el env
reducido de `_verify_pos_config`, usando `sudo()` solo puntual sobre un campo
`readonly` tras validar ownership).

- `session_orders`: no devolver el histórico completo de la caja; acotar a las
  órdenes cuyo token por-orden presente el cliente; tope duro de `limit`; no
  exponer `vat`/`phone` del partner en el listado.
- `write_mf_invoice_data`: exigir `consteq()` del token por-orden; rechazar si la
  orden ya tiene `mf_invoice_number` o si su `account.move` está `posted`.
- `create_invoice`: exigir `consteq()` del token por-orden antes de facturar.
- `identify`: correr sin `sudo()` (dejar aplicar record rules), no devolver
  `phone`, desempate determinista entre duplicados de cédula, rate-limit por token.

### 2. Identificación de cliente por cédula/RIF (endurecimiento)

- `identify_create`: deduplicar reusando el `search` de `identify` antes de
  `create` (devolver el existente); validar formato de cédula (V/E numérica) y
  RIF (J/G) en cliente (`identification_page.js`) y servidor; rate-limit.

### 3. Correctitud fiscal

- `foreign_amount_total` de cabecera consistente con el `amount_total` que
  persiste el controller del core (derivarlo de `sum(lines.price_subtotal_incl)`,
  no del `amount_total` intermedio de `super().recompute_prices()`), para que la
  invariante `foreign_amount_total == convert(amount_total)` se sostenga bajo
  `round_globally` (default de compañía en Odoo 19).
- Convertir el **monto de pago** a moneda fiscal en `buildKioskFiscalPayload`
  (hoy las líneas se convierten pero el pago no → descuadre pago≠total en la MF
  cuando la moneda base ≠ VES).
- Guard de reentrada en `confirmationPage` (auto-print) y manejo del fallo de
  persistencia del número fiscal, para evitar doble emisión de documento fiscal.

### 4. Cobertura de tests (deuda de mayor riesgo)

- `HttpCase` para las 5 rutas públicas (orden ajena rechazada, idempotencia y
  rollback de `create_invoice`, cédula inexistente/existente, duplicada, RIF
  inválido).
- Test de la facturación diferida (`_process_saved_order`/
  `_generate_pos_order_invoice`/`kiosk_defer_invoice`).
- Tests Python del módulo `l10n_ve_pos_mf_self_order` (auto_install, hoy sin
  `tests/`) y unit tests JS del Kiosko (`kiosk_sync_queue.js`,
  `buildKioskFiscalPayload`).
- Completar `test_04b` (rama `not tax_ids` multi-compañía) y hacerlo hermético.

### 5. Menores / mantenibilidad

Notas de estilo y robustez (ver `tasks.md` §6): `_send_payment_result` sin
`super()`, N+1 en `recompute_prices`, `except Exception` amplio, teardown de
listener/timer en la cola, versión de manifest no estándar, xpath por clases de
presentación.

## Capabilities

### New Capabilities

- `pos-self-order-kiosk-endpoint-security`: las rutas públicas del Kiosko
  aplican control de acceso por **token por-orden** (no solo `config_id`),
  operan con privilegio reducido (sin `sudo()` general) y exponen el mínimo de
  datos del partner, cerrando la fuga de PII y la manipulación de órdenes ajenas.

### Modified Capabilities

- `pos-self-order-kiosk-identification`: la identificación/creación de partner
  deduplica, valida formato y limita tasa.
- `pos-self-order-kiosk-invoice-recovery`: los endpoints de recuperación
  (`session_orders`, `create_invoice`) exigen token por-orden.
- `pos-self-order-kiosk-fiscal-print`: totales foráneos y monto de pago fiscal
  consistentes; sin doble emisión.

## Impact

- **`l10n_ve_pos_self_order`** (dueño): `controllers/orders.py` (token por-orden,
  quitar `sudo`, cap de `limit`, dedup), `models/res_partner.py` (no exponer
  `vat`/`phone` en el canal público de listado), `models/pos_order.py`
  (`recompute_prices` consistente), `identification_page.js` (validación de
  formato), y tests (`HttpCase` + diferido).
- **`l10n_ve_pos_mf_self_order`**: `controllers/main.py` (token por-orden +
  guards de estado/no-sobrescritura en `write_mf_invoice_data`),
  `fiscal_payload.js` (conversión del pago), `self_order_fiscal.js` (guard de
  reentrada + fallo de persistencia), y `tests/` nuevo.
- **`l10n_ve_pos_mf`**: evaluar mover los guards de estado/no-sobrescritura al
  propio `write_mf_invoice_data` (defensa en profundidad; el uso autenticado
  desde la caja no se ve afectado).
- **`l10n_ve_accountant`**: solo test (`test_04b`).
- **Riesgo:** medio. El cambio de control de acceso toca el contrato de datos que
  consume el frontend del Kiosko (el panel de recuperación pasa a necesitar el
  token por-orden guardado en el dispositivo, patrón `get_orders_by_access_token`
  del core). Requiere tests server-side que ejerzan el rechazo de orden ajena.
- **Fuera de alcance:** rediseñar el modelo de tokens del Kiosko; cambios en la
  caja (`binaural_megasoft`); reintento automático (cron) de facturación diferida.

References: revisión IA del PR
https://github.com/binaural-dev/odoo-venezuela/pull/1161 · Tarea 78767 (Autopago
POS V19) https://binaural.odoo.com/odoo/action-341/78767 · precondiciones
[[l10n-ve-pos-self-order-kiosk-invoice-recovery]],
[[l10n-ve-pos-self-order-kiosk-partner-identification]]
