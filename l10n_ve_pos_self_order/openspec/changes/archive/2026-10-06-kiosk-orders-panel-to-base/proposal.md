# Feature: panel de órdenes y shell de debug del Kiosko, en base

## Why

El panel de órdenes del Kiosko (listar la sesión, ver el detalle y **recuperar la
factura** de una orden pagada pendiente) y el shell de Debug que lo abre vivían
en `l10n_ve_pos_mf_self_order` (el módulo de máquina fiscal). Pero la
**recuperación de factura NO es fiscal**: el endpoint `create_invoice`, el
diferido de facturación (`_process_saved_order`/`_generate_pos_order_invoice`) y
la cola durable de reintento del registro (`kiosk_sync_queue.js`) ya viven en
ESTE módulo, que es el que gobierna el ciclo de vida de la orden del Kiosko.

Consecuencias del reparto anterior:

1. **Un Kiosko sin máquina fiscal no tenía UI de recuperación**: solo el menú de
   backend. Si `l10n_ve_pos_mf_self_order` no estaba instalado (no hay MF), no
   había forma de crear desde el Kiosko la factura de una orden que quedó pagada
   pendiente de facturar.
2. **Concerns mezclados**: los botones "Reintentar registro pendiente/FALLIDAS"
   operan sobre la cola de persistencia de base, pero estaban en el diálogo de
   Debug del módulo fiscal.
3. El loader `session_orders` (datos genéricos de la orden: líneas, pago,
   partner) también estaba en el módulo fiscal pese a no pedir ningún dato
   fiscal.

## What Changes

Se traslada a `l10n_ve_pos_self_order` **todo lo genérico** del panel y el debug,
dejando en el módulo fiscal solo los *agregados* (estado fiscal +
imprimir/reimprimir), que se enganchan por extensión.

- **Loader `session_orders`** → ruta pública `/l10n_ve_pos_self_order/kiosk/session_orders`.
  Devuelve `pos.order`/`line`/`payment`/`partner` genéricos; los campos fiscales
  (`mf_invoice_number`…) se añaden solos cuando el módulo fiscal está instalado
  (extiende `_load_pos_self_data_fields`), así el panel funciona con o sin MF.
- **Servicio de recuperación** (`self_order_recovery.js`): getter
  `kioskSessionOrders` (listado genérico) + `createKioskInvoice` (crear factura de
  una pendiente).
- **`KioskOrdersDialog`** (componente + plantilla): panel con dos estados base
  —`pending_invoice`/`invoiced`— y una acción, **Crear factura**. La plantilla
  expone anclas (`o_kiosk_order_badges|status|payment|actions`) para que el módulo
  fiscal inyecte por `t-inherit` sus badges/estado/botones.
- **`KioskDebugDialog`** (componente + plantilla): shell de debug con **Ver
  órdenes** + **Reintentar registro pendiente/FALLIDAS** (cola de base). Ancla
  `o_kiosk_debug_view_orders` para que el módulo fiscal inserte sus botones de
  máquina fiscal.
- **Botón flotante** "🛠 Debug Kiosko" (solo `?debug=1`) que abre el shell; un
  SOLO botón, extendido por MF (no un segundo botón).
- **i18n**: `es_VE.po` nuevo y **completo** para todo el panel/debug (source en
  inglés + traducción), evitando el problema previo de strings sin traducir.

`orderStatus` base deriva "facturada" de `state === "invoiced"` (señal
autoritativa del servidor, más fiable que un flag client-side que puede no venir
en órdenes cargadas del server).

## Non-goals

- No cambia la lógica server-side de recuperación (`create_invoice`, savepoints,
  menú de backend): ya estaba aquí y se mantiene igual.
- No toca la impresión/reimpresión fiscal ni el estado fiscal: eso lo aporta
  `l10n_ve_pos_mf_self_order` extendiendo lo de aquí.
