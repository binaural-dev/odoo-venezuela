## Context

El flujo de pago del Kiosko tiene hoy un punto único de fallo: la **atomicidad
orden+factura**. El controlador del core `pos_self_order` (`process_order`) crea/
actualiza la `pos.order` y llama a `pos.payment.method._payment_request_from_kiosk`;
en el flujo Megasoft (`binaural_megasoft_self_order`) eso ejecuta
`order._process_saved_order(False)`, que **factura** en la misma transacción. Un
`ValidationError` al facturar (config fiscal SENIAT, secuencia, impuesto, dato
del partner) hace rollback de TODO el request → se pierde la orden y el pago,
pese a que la tarjeta ya se cobró en el VPOS (aprobación client-side).

El ciclo de vida de la orden del Kiosko lo gobierna `l10n_ve_pos_self_order`: aquí
se fuerza `to_invoice=True` (`_check_pos_order`), se mantienen los totales
foráneos (`recompute_prices`) y vive la cola de reintento (`kiosk_sync_queue.js`).
Por eso la resiliencia de facturación es de ESTE módulo, no del de la máquina
fiscal (que solo consume el resultado para imprimir).

Además, la respuesta del VPOS (que en `accion:"tarjeta"` trae
`codRespuesta, mensajeRespuesta, numeroAutorizacion, numeroReferencia,
numeroLote, numeroTarjeta, tipoTarjeta, nombreAutorizador, tid, nombreVoucher`,
confirmado en el manual MAET-VPOSW-00_MAY.2025) se descarta tras validar
`codRespuesta === "00"`. Nadie la persiste — ni la caja ni el Kiosko —, así que
no hay prueba durable del cobro con la que conciliar una orden a medio facturar.

## Goals / Non-Goals

**Goals:**
- Que un pago aprobado SIEMPRE deje una orden creada y pagada en Odoo, aunque la
  facturación (contable y/o fiscal) falle.
- Convertir la facturación en un paso diferido, reintentable e idempotente,
  **agnóstico al método de pago** (no atado a Megasoft).
- Persistir la verificación de pago Megasoft como registro durable.
- Dar al operador un camino de recuperación claro (panel del Kiosko fuera de
  debug) y a contabilidad otro (menú de backend).

**Non-Goals:**
- Reintento automático (cron) de la facturación pendiente (v1 es manual).
- Persistir el JSON del VPOS en la caja (`binaural_megasoft`).
- Cambiar el bloqueo de la línea de pago aprobada en la caja
  (`payment_status="done"`): fuera de alcance, no se toca la caja.
- Paridad offline completa del Kiosko (empezar órdenes durante un corte total).

## Decisions

### D1 — La resiliencia va en el seam de facturación de `l10n_ve_pos_self_order`, no en Megasoft

El override que envuelve la facturación en un `savepoint` se hace en `pos.order`
dentro de `l10n_ve_pos_self_order`, gateado a `self_ordering_mode == 'kiosk'`. Es
el módulo correcto: ya es el que fuerza `to_invoice` en el Kiosko. Ventajas sobre
refactorizar `_payment_request_from_kiosk` (Megasoft):
- **Agnóstico al método de pago:** cualquier flujo del Kiosko que facture (Megasoft
  hoy, un terminal mañana) queda protegido con un solo override.
- **Menos churn en Megasoft:** `_payment_request_from_kiosk` sigue llamando a
  `_process_saved_order` tal cual; Megasoft solo gana la persistencia del JSON.

Alternativa descartada (facturación 100% asíncrona vía `queue_job`/cron): añade
dependencia e infraestructura, y difiere innecesariamente el camino feliz.

**Seam a confirmar en implementación:** hoy `_process_saved_order(False)` hace
paid+picking+costo+factura junto. Hay que envolver únicamente el tramo de
facturación. Opciones a evaluar contra el código de `pos.order` en Odoo 19:
- (a) overridear el método que genera la factura (`_generate_pos_order_invoice()`
  / `_create_invoice()` según la API v19) y envolver el `super()` en
  `try/savepoint`, gateado a kiosko; o
- (b) overridear `_process_saved_order` y, en modo kiosko, ejecutar el tramo de
  pago normal pero facturar en un savepoint aparte.
Se prefiere (a) si el método de facturación es aislable limpio; (b) es el
fallback. La tarea 2.1 exige verificar el método real antes de codificar.

### D2 — Estado "pendiente de facturar" = estado nativo, sin flag nuevo

La orden pendiente de facturar es exactamente `state='paid'` + `to_invoice=True`
+ `account_move` vacío. No se inventa un campo de estado nuevo: se deriva de esos
tres. El menú de backend y el panel filtran por esa condición. Si un `computed`
`kiosk_invoice_pending` (`store=False`) facilita el dominio de la vista, se añade
sobre esa misma condición; decisión menor, no arquitectónica.

### D3 — Endpoint de facturación diferida: genérico (self_order), no fiscal

El endpoint público que crea la factura de una orden pendiente vive en
`l10n_ve_pos_self_order/controllers/orders.py` (junto a los de identificación),
NO en el módulo fiscal: facturar no es una operación fiscal-de-máquina, es del
ciclo de vida de la orden. El panel del MF y el menú de backend lo consumen. Es
idempotente (guarda por `account_move`) y valida `access_token` + pertenencia a
la caja, igual que `write_mf_invoice_data`.

### D4 — Persistencia del JSON: raw + subconjunto, en `pos.payment`, en el puente Megasoft

Se guarda el JSON crudo (`megasoft_vpos_response`, `Text`) como auditoría y un
subconjunto tipado para mostrar sin re-parsear: `megasoft_auth`
(numeroAutorizacion), `megasoft_reference` (numeroReferencia), `megasoft_lote`
(numeroLote), `megasoft_card` (numeroTarjeta enmascarada), `megasoft_card_type`
(tipoTarjeta), `megasoft_bank` (nombreAutorizador), `megasoft_resp_code`
(codRespuesta). Van en `binaural_megasoft_self_order` (Kiosko), no en la caja,
para no tocar `binaural_megasoft`. Trade-off: si mañana la caja quiere lo mismo,
habrá que promover los campos (migración de columnas trivial). Aceptado.

**Confianza:** el JSON llega del cliente (el VPOS es local al navegador). Es el
mismo modelo de confianza ya vigente (el cliente afirma `codRespuesta==="00"`);
no se amplía superficie: solo se guarda lo que el cliente ya usaba para decidir.

### D5 — No auto-imprimir fiscal si la factura contable está pendiente

`confirmationPage` (en `l10n_ve_pos_mf_self_order`) añade la guarda
`order.account_move` antes de auto-imprimir. Emitir un número fiscal para una
orden sin factura contable crearía un desfase (número fiscal sin `account.move`
donde estamparlo por `write_mf_invoice_data`). Se deja pendiente y se resuelve en
orden desde el panel: **crear factura → imprimir fiscal → persistir número**.
Refina —no contradice— el invariante de `pos-self-order-kiosk-fiscal-print`
("nunca imprimir sin orden en Odoo"): ahora, para el auto-print, es "nunca
imprimir sin FACTURA en Odoo". La impresión manual desde el panel sigue disponible
una vez creada la factura.

### D6 — Recuperación desde dos frentes: Kiosko (operador) y backend (contabilidad)

- **Panel del Kiosko** (`kiosk_fiscal_orders_dialog`): recuperación en sitio.
  Reutiliza `session_orders` (ya trae paid/done/invoiced) + el endpoint
  `create_invoice`.
- **Menú de backend**: vía autoritativa. Cuando la causa es de configuración,
  contabilidad la corrige y factura las pendientes desde Odoo. Panel y menú
  llaman al MISMO código de facturación server-side (idempotente).

### D7 — Recuperación solo en modo debug (sin botón de cara al cliente)

La recuperación se abre desde el menú de Debug MF (`?debug=1`) → "Órdenes
fiscales". Se descartó un botón visible en la raíz del Kiosko: es una tarea de
operador/soporte, no de cara al cliente, y un botón permanente en el autoservicio
confunde al comprador. Para contabilidad, la vía autoritativa es el menú de
backend (D6). (Decisión del usuario tras revisar una primera versión con botón
visible.)

## Risks / Trade-offs

- **[Riesgo] Descomponer el seam de facturación.** Envolver mal el savepoint
  podría dejar picking/costo a medias o no aislar la factura. → Mitigación: tests
  server-side (factura falla → orden queda paid+pendiente, con pago y picking;
  factura OK → estado final normal) y estudio del método v19 antes de codificar
  (tarea 2.1).
- **[Riesgo] Doble factura al reintentar.** → Mitigación: guarda por
  `account_move`; endpoint y menú comparten el mismo código idempotente.
- **[Riesgo] Confianza en el JSON del cliente.** → Igual que hoy; no se amplía la
  superficie (D4). Se guarda como auditoría, no como autorización.
- **[Trade-off] Campos Megasoft solo en el Kiosko.** Divergencia potencial con la
  caja si mañana quiere lo mismo. Aceptado (D4).
- **[Trade-off] Recuperación manual (sin cron).** El operador/contabilidad deben
  actuar. Aceptado para v1; cron como mejora futura.

## Migration Plan

Sin migración de datos destructiva. Los campos nuevos en `pos.payment` son
columnas aditivas (nulas para pagos existentes). El estado "pendiente de
facturar" es nativo, no requiere data-fix. Reversible revirtiendo los módulos;
las órdenes ya facturadas no se ven afectadas.
