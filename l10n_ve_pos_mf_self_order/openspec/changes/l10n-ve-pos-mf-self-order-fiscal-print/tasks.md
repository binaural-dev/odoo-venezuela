# Tasks

## 1. Diagnóstico (hecho — solo lectura)

- [x] 1.1 Punto de entrada fiscal de la caja:
      `OrderPaymentValidation.finalizeValidation` → `PosStore.pushToMF` →
      `get_data_invoice`/`_convertOrderForDriver` → `window.fiscalPrinter`
      (`TfhkaDriver`). Comunicación 100% client-side (Web Serial), sin RPC.
- [x] 1.2 El driver (`l10n_ve_mf_base/static/src/{core,drivers}/*.js`) es
      autocontenido (solo `navigator.serial`), reutilizable en cualquier bundle.
- [x] 1.3 El Kiosko es online-first: `pos_self_order/.../data_service.js`
      desactiva IndexedDB y la cola local en modo kiosko (no-op salvo `mobile`);
      hay `NetworkConnectionLostPopup` que pide esperar conexión.
- [x] 1.4 Flujo de confirmación del Kiosko: `CartPage.pay` →
      `SelfOrder.confirmOrder` → `sendDraftOrderToServer` (RPC
      `/pos-self-order/process-order/kiosk`) → `confirmationPage()` (pago en
      caja) o `payment` (terminal); Megasoft confirma por bus `PAYMENT_STATUS`.
- [x] 1.5 `account.tax`, `pos.payment.method`, `product.*` SÍ se cargan en el
      dataset del Kiosko (`pos_config.py:305-307`); el producto ordena por
      `default_code`. Exponer `fiscal_code`/`code_fiscal_printer` vía
      `_load_pos_self_data_fields` llega al cliente.

## 2. Backend — exponer datos fiscales al Kiosko (hecho)

- [x] 2.1 Módulo puente `l10n_ve_pos_mf_self_order`: manifest
      (`auto_install`, assets en `pos_self_order.assets` con el driver de
      `l10n_ve_mf_base`), `__init__`, `models/__init__`.
- [x] 2.2 `pos.config._load_pos_self_data_fields`: campos fiscales
      (`flag_21`, `serial_machine`, `has_cashbox`, `traditional_line`,
      `access_button_mf`, `mf_skip_invoice_pdf`, `enable_auto_sync`,
      `auto_sync_interval`, `message_in_head`, `receipt_header/footer`).
- [x] 2.3 `pos.payment.method._load_pos_self_data_fields`: `code_fiscal_printer`.
- [x] 2.4 `account.tax._load_pos_self_data_fields`: `fiscal_code`.
- [x] 2.5 `pos.order._load_pos_self_data_fields`: `mf_invoice_number`,
      `fiscal_machine`, `mf_reportz` (para que el número fiscal viaje en
      `serializeForORM` y se estampe en el `account.move` al sincronizar).

## 3. Builder del payload del Kiosko (Fase 1) — SIN tocar PosStore

- [x] 3.1 Builder propio `static/src/app/fiscal_payload.js`
      (`buildKioskFiscalPayload`): produce la MISMA forma que consume
      `TfhkaDriver.printInvoice` (partner, lines, payment_lines explícitas,
      header/footer/additional, flag_21, has_cashbox), para el caso simple del
      Kiosko. Helpers propios (`normalizeProductName`, `extractReceiptLines`).
      **No toca `PosStore`.** Precio de línea NETO de descuento (el driver no
      recibe `discount`).
- [x] 3.2 Precio foráneo por línea = `price_unit * order.foreign_currency_rate`
      redondeado con la moneda foránea (espejo de `localToForeign`), con
      cortocircuito `vef_base` si la moneda base ya es VES. Pago = monto VES
      aprobado (código local → cierre `1XX` tolerante, no divisa).

## 4. Frontend Kiosko — impresión fiscal (Fase 1)

- [x] 4.1 Cargar el driver en el bundle (vía manifest — `l10n_ve_mf_base/{core,
      drivers}/*.js` en `pos_self_order.assets`). Pendiente verificar en navegador
      que `window.fiscalPrinter` no colisione si conviven POS de caja + Kiosko.
- [x] 4.2 Conexión al puerto (Kiosko DESATENDIDO — sin botón de cara al cliente):
      patch de `SelfOrder.setup` que auto-conecta silenciosamente al arrancar
      (`ensureFiscalPrinterConnected`, gated por `kioskMode` + `access_button_mf`),
      + helper `pairFiscalPrinter` (pareo manual con gesto, para modo debug), +
      `getFiscalPrinter`/`useFiscalMachine`. Reutiliza `window.fiscalPrinter`
      (`TfhkaDriver`) verbatim. Falta: panel debug que exponga `pairFiscalPrinter`
      (tarea 6.2).
- [x] 4.3 Builder invocado con `selfOrder.currentOrder` + config/currency +
      `payment_lines` EXPLÍCITAS (método aprobado + monto), porque el pago se
      registra server-side y la orden del cliente no tiene `payment_ids` al
      imprimir. (Ver 3.1.)
- [x] 4.4 `SelfOrder.printKioskFiscalInvoice(order, {paymentMethod, amount})`:
      conecta driver → `buildKioskFiscalPayload` → `printInvoice(payload)` →
      guarda `mf_invoice_number`/`fiscal_machine`/`mf_reportz` en la orden.
      Idempotente (`!order.mf_invoice_number`). Espejo de
      `set_data_from_fiscal_machine`.

## 5. Resiliencia — imprimir-primero / sincronizar-después (Fase 2)

- [x] 5.1 Enganche Megasoft (`binaural_megasoft_self_order/.../payment_page.js`):
      en `_finalizeMegasoftPayment`, imprimir fiscal ANTES del RPC
      `/kiosk/payment` (`_printMegasoftFiscalInvoice`, delega en
      `SelfOrder.printKioskFiscalInvoice`). Guardado (modo simulación + módulo
      fiscal ausente); si falla NO bloquea ni recobra (queda para reimprimir en
      debug). El nº fiscal se guarda en la orden ANTES del `serializeForORM` del
      RPC → viaja al servidor con la orden.
- [~] 5.2 Enganche pago-en-caja: FUERA DE ALCANCE por ahora — en pago-en-caja
      (sin terminal) el cobro y la factura fiscal los hace el CAJERO, no el
      Kiosko. Reevaluar solo si aparece un caso de Kiosko que factura sin cobrar.
- [ ] 5.3 Persistencia + reintento reutilizando el motor del POS: reactivar
      IndexedDB del `PosData` (hoy no-op en kiosko) **solo para las órdenes
      pendientes** — NO para cachear el dataset del servidor (el kiosko lo apaga
      a propósito). Cola/reintento calcada del patrón `network.unsyncData` +
      `syncData()`, pero disparando el **RPC público del kiosko**
      (`/pos-self-order/process-order` / `/kiosk/payment`), no el `sync_from_ui`
      autenticado (inaccesible desde el frontend público). Reintento en `online`/
      al cargar. La orden nunca se pierde; al sincronizar, el servidor registra
      pago + `account.move` con el número fiscal.
      - [ ] 5.3.1 Verificar qué reactivar exactamente de `data_service.js` sin
            arrastrar el caché de datos del servidor ni el borrado de órdenes
            "faltantes" (`checkAndDeleteMissingOrders`, no-op en kiosko).
- [ ] 5.4 Idempotencia: no reimprimir si la orden ya tiene `mf_invoice_number`
      (espejo de la guarda `!order.mf_invoice_number` de la caja); no recobrar la
      tarjeta en reintentos.

## 6. Reimpresión de fallidas + fallos (Fase 3)

- [ ] 6.1 Al fallar la impresión: persistir el payload armado en local (cola
      "pendiente de imprimir") sin recobrar.
- [ ] 6.2 Acción de reimpresión gated por modo debug: lista de facturas
      pendientes de imprimir + reenvío a la máquina (`printInvoice(payload)`).
- [ ] 6.3 Respaldo en caja: la orden queda marcada para reimprimir desde el POS
      de caja (`write_mf_invoice_data` / `PrintPendingOrderButton`).

## 7. Tests (Python; el usuario los corre — convención del repo)

- [ ] 7.1 `_load_pos_self_data_fields` de config/payment_method/tax/order incluye
      los campos fiscales esperados.
- [ ] 7.2 (Si aplica server-side) el `account.move` de la orden del Kiosko
      sincronizada lleva `mf_invoice_number`/`mf_serial`/`mf_reportz`.

## 8. Verificación manual (navegador, por el usuario)

- [ ] 8.1 Kiosko con máquina fiscal conectada: completar orden → se imprime la
      factura fiscal al confirmar; el `mf_invoice_number` queda en la orden.
- [ ] 8.2 Simular servidor caído tras aprobar el pago: la factura se imprime
      igual y la orden se sincroniza sola al volver la conexión.
- [ ] 8.3 Forzar fallo de impresión → reimprimir desde modo debug sin recobrar.
- [ ] 8.4 Regresión (sanity): caja normal (cajero) imprime fiscal igual — no se
      tocó `PosStore` ni el driver; solo se comparte `window.fiscalPrinter` si
      conviven en el mismo navegador.

## 9. OpenSpec

- [x] 9.1 Proposal + spec delta + tasks escritos.
- [ ] 9.2 `openspec change validate l10n-ve-pos-mf-self-order-fiscal-print`
      → válido.
