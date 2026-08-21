# Tasks

> Origen: revisión IA del PR #1161. Severidad: 🔴 bloqueante · 🟡 importante ·
> 🟢 menor. Rutas relativas a la raíz del repo. Verificado contra core 19.0
> (`addons/pos_self_order/controllers/orders.py`): el core usa `consteq()` del
> token por-orden y un env de privilegio reducido de `_verify_pos_config`.

> **Decisión de implementación (mantener `sudo`).** El Kiosko se abre con un
> usuario deliberadamente capado (solo ve el Kiosko) y aun así debe traer toda
> la info que necesita, así que las rutas SIGUEN corriendo con `sudo()`. El
> objetivo de seguridad no era "quitar sudo" sino "que el token del dispositivo
> no dé acceso a datos arbitrarios": ese enforcement se hace **en el
> controlador** (proyección mínima, guards de estado, rate-limit, tope de
> `limit`), no delegándolo en las record rules (que con un usuario capado no
> filtrarían nada y además romperían el Kiosko). Por eso §1.5 se **reinterpreta**
> (no se quita el `.sudo()`) y en el spec el requirement "privilegio reducido"
> se sustituye por "sudo + enforcement en el controlador".

> **Decisión (token por-orden DESCARTADO).** Las rutas `session_orders`,
> `create_invoice` y `write_mf_invoice_data` NO se acotan por token por-orden.
> El panel que las consume es una **herramienta de administrador** (tras el gate
> de Debug con PIN supervisor, [[binaural-pos-hr-self-order-debug-gate]]) cuyo
> propósito es, sobre CUALQUIER orden de la caja: recuperar/crear factura,
> reimprimir la factura fiscal, etc. Acotar por token por-orden rompería esa
> función. El control de acceso al panel es el **PIN de supervisor** en el
> cliente, no un token por-orden. Se mantienen los guards que NO estorban al
> admin (tope de `limit`, no-sobrescritura de número fiscal). Riesgo residual
> aceptado: quien lea el token del dispositivo puede llamar a estas rutas a mano
> (kiosko en red interna).

## 1. Control de acceso de rutas públicas (🔴 bloqueante)

- [~] 1.1 🔴 `session_orders` — `l10n_ve_pos_self_order/controllers/orders.py`.
      HECHO (lo que aplica). Tope duro `limit = min(int(limit or 50), 200)`; el
      panel llama sin `limit` → usa el default 50 (sin regresión). Se MANTIENE
      `sudo`. Token por-orden y quitar `vat`/`prefix_vat`: DESCARTADOS (decisión
      arriba — el panel de admin necesita ver todas las órdenes y su `vat` para
      reimprimir la copia fiscal).
- [~] 1.2 🔴 `write_mf_invoice_data` — `l10n_ve_pos_mf_self_order/controllers/main.py`.
      PARCIAL. HECHO (servidor-solo, sin cambio de cliente): guard de integridad
      en la ruta pública — rechaza si `order.mf_invoice_number` ya existe (no
      re-numera un correlativo SENIAT). CORRECCIÓN al plan: NO se añade el guard
      "rechazar si `account_move.state == 'posted'`" — escribir el número fiscal
      sobre una factura ya posteada ES el flujo normal en VE; ese guard rompería
      el caso legítimo. El guard útil y seguro es el de no-sobrescritura (un
      reintento legítimo llega con el campo vacío, así que no lo bloquea).
      El guard rechaza solo si llega un número DISTINTO al ya persistido;
      reenviar el MISMO (reintento de persistencia §3.4) es no-op y se permite.
      Verificado que la reimpresión NO re-llama a `write_mf` (usa
      `reprintKioskFiscalCopy`/`reprintDocument`), así que el guard no la estorba.
      Token por-orden: DESCARTADO (decisión arriba). Los guards se pusieron SOLO
      en la ruta pública (no en el modelo `l10n_ve_pos_mf/models/pos_order.py:88`)
      para no arriesgar el flujo autenticado de la caja.
- [x] 1.3 🔴 `identify` — `l10n_ve_pos_self_order/controllers/orders.py`.
      HECHO. Mantiene `sudo()` (decisión arriba). Ya NO devuelve `phone`; en su
      lugar un flag `has_phone` para que el Kiosko sepa si pedir el teléfono
      faltante. Desempate determinista de duplicados vía
      `order="is_company desc, id asc"` (helper `_ve_find_partner`). Rate-limit por
      `access_token` (`_ve_within_rate_limit`, ventana deslizante en memoria del
      worker, calibrada para no tocar la fila real). No se acota por compañía
      (partners no scopeados en este código; con `sudo` no aplicaría igual).
- [~] 1.4 🟡 `create_invoice` — `l10n_ve_pos_self_order/controllers/orders.py`.
      Token por-orden DESCARTADO (decisión arriba): el admin debe poder crear la
      factura de CUALQUIER orden pendiente de la caja desde el panel. Se deja tal
      cual (valida `config_id` + idempotente). Sin cambios.
- [~] 1.5 🟡 REINTERPRETADO (ver Decisión de implementación). NO se quita el
      `.sudo()`: el Kiosko corre con un usuario capado y necesita `sudo` para
      traer los datos. En su lugar, el enforcement va en el controlador: token
      por-orden (`consteq`) en las rutas de orden (§1.1, §1.2, §1.4), proyección
      mínima de PII, guards de estado, y rate-limit en las de identificación.
      Archivos: `l10n_ve_pos_self_order/controllers/orders.py`,
      `l10n_ve_pos_mf_self_order/controllers/main.py`.

## 2. Identificación por cédula/RIF (🟡)

- [x] 2.1 🟡 `identify_create` — HECHO. Deduplica reusando `_ve_find_partner`
      (mismo `search` que `identify`) y devuelve el existente antes de `create`.
      Si el existente NO tiene teléfono y el cliente lo envió, lo rellena
      (fill-only). Valida formato (V/E, J/G numéricos) en servidor
      (`_ve_vat_format_error`). Nueva ruta `identify/set_phone` para completar el
      teléfono de un cliente existente sin él (fill-only, re-localiza por cédula,
      nunca sobrescribe).
- [x] 2.2 🟡 `identification_page.js` — HECHO. Valida formato de cédula/RIF en
      cliente (`vatFormatError`, usada en `onIdentify`/`onCreate`). Nuevo paso
      `phone` cuando `has_phone` es falso; teléfono requerido al crear y al
      completar (regla de negocio: registrar el teléfono siempre que falte).
- [x] 2.3 🟡 Rate-limit / anti-abuso en `identify`/`identify_create`/`set_phone`
      (por `access_token`). En memoria del worker; devuelve un error suave que el
      Kiosko muestra, sin cortar la fila real.

## 3. Correctitud fiscal (🟡)

- [ ] 3.1 🟡 `recompute_prices` — `l10n_ve_pos_self_order/models/pos_order.py:53`.
      Derivar `foreign_amount_total` de la MISMA cantidad que persiste el controller
      del core (`sum(self.lines.mapped('price_subtotal_incl'))`), no del
      `amount_total` intermedio de `super()`. Mantiene la invariante
      `foreign_amount_total == convert(amount_total)` bajo `round_globally` (default
      Odoo 19). `line.foreign_price` no tiene el problema (parte de `price_unit`).
- [ ] 3.2 🟡 `buildKioskFiscalPayload` — `l10n_ve_pos_mf_self_order/static/src/app/fiscal_payload.js`.
      Convertir `payAmount` a moneda fiscal con el mismo `toFiscal()` que las líneas
      (hoy toma `order.payment_ids[].amount` en moneda base sin convertir → descuadre
      pago≠total cuando la base ≠ VES).
- [ ] 3.3 🟡 `confirmationPage` — `l10n_ve_pos_mf_self_order/static/src/overrides/self_order_fiscal.js:66`.
      Guard de reentrada por orden (el bus `PAYMENT_STATUS` puede reentrar antes de
      que se setee `mf_invoice_number`) → evitar doble impresión.
- [ ] 3.4 🟡 Fallo de persistencia del número fiscal — `self_order_fiscal.js`
      (`_persistKioskFiscalNumber`). Si `write_mf_invoice_data` falla tras imprimir,
      marcar la orden como "impresa pendiente de persistir" y reintentar el `write`
      (NO reimprimir): hoy, tras un reload, la orden se ve "sin imprimir" y
      `printOrReprintKioskOrder` emitiría un documento fiscal NUEVO.

## 4. Tests (🟡 — la deuda de mayor riesgo)

- [ ] 4.1 🟡 `HttpCase` para las 5 rutas públicas: `identify` (cédula
      inexistente→[] vs existente), `identify_create` (cédula duplicada→no crea dos;
      RIF inválido→rechaza), `create_invoice` (idempotente si ya hay `account_move`;
      rollback si la factura no llega a `posted`; **orden de OTRA caja→rechazada**),
      `session_orders` (**orden de otra caja/otro token→no aparece**),
      `write_mf_invoice_data` (**orden ajena→rechazada**; no sobrescribe número
      existente; no toca move `posted`).
- [ ] 4.2 🟡 Facturación diferida — `l10n_ve_pos_self_order/models/pos_order.py:74`
      (`_process_saved_order`) y `:107` (`_generate_pos_order_invoice`). Forzar un
      fallo de factura (diario/secuencia inválidos) y assert: orden queda `paid` +
      `to_invoice` sin `account_move`; el savepoint revierte el borrador no-`posted`;
      la ruta explícita (sin `kiosk_defer_invoice`) SÍ propaga el error.
- [ ] 4.3 🟡 Crear `l10n_ve_pos_mf_self_order/tests/` (módulo auto_install hoy sin
      tests Python): cubrir `_send_payment_result` (que el payload del bus incluye
      `pos.payment`) y los `_load_pos_self_data_fields` fiscales (estado instalado).
- [ ] 4.4 🟡 Unit tests JS del Kiosko: `kiosk_sync_queue.js` (clasificación
      `ConnectionLostError`→conservar cola vs error de negocio→`failed`, nunca
      descartar; `retryFailedKioskRegistrations`), y `buildKioskFiscalPayload` (las
      ~6 ramas de validación, conversión fiscal, neteo de descuento, `fiscal_code`
      strip `t`, `prefix_vat+vat`, `normalizeProductName` ya está `export`ada).
- [ ] 4.5 🟡 `l10n_ve_accountant/tests/test_product_template.py:88` (`test_04b`):
      agregar la rama `not tax_ids` multi-compañía (producto con impuestos SOLO de
      otra compañía → conserva los ajenos + agrega el default propio); fijar el
      `account_sale_tax_id` del `base.main_company` en el propio test (hermético);
      assert de "no error" en el lado venta.
- [ ] 4.6 🟡 `res_partner._load_pos_self_data_read` —
      `l10n_ve_pos_self_order/models/res_partner.py`: `TransactionCase` que verifique
      el contrato de read consumido por Megasoft (`binaural_megasoft_self_order`).

## 5. Verificación

- [ ] 5.1 Correr la suite completa de los 4 módulos afectados; coverage de los
      controllers públicos y del diferido > 0 (hoy es el hueco).
- [ ] 5.2 Confirmar que el camino feliz del Kiosko (identificar → escanear →
      pagar → facturar → imprimir MF) no cambia observablemente.
- [ ] 5.3 Manual: intentar acceder a una orden de otra caja/otro token por cada
      ruta → debe rechazar.

## 6. Menores / mantenibilidad (🟢 — opcional)

- [ ] 6.1 `l10n_ve_pos_mf_self_order/models/pos_order.py:25` `_send_payment_result`
      reemplaza el core sin `super()` (fiel hoy; deja comentario del riesgo de
      upgrade o busca un hook para no reimplementar el payload).
- [ ] 6.2 `l10n_ve_pos_self_order/models/pos_order.py:69` `recompute_prices`
      escribe `foreign_price` línea por línea (N+1); agrupar si se quiere.
- [ ] 6.3 `l10n_ve_pos_self_order/models/pos_order.py:130` `except Exception` amplio
      en el diferido (mitigado con `_logger.exception` + savepoint; acotar si se
      puede).
- [ ] 6.4 `kiosk_sync_queue.js`: teardown del listener `online` y del timer
      (`browser.clearInterval`); `retryFailedKioskRegistrations` reporta `remaining`
      inexacto ante `ConnectionLostError` (quedan en `pending`, no en `failed`).
- [ ] 6.5 `l10n_ve_pos_self_order/__manifest__.py:8` versión `"1.2"` → `19.0.1.0.0`
      (consistencia con el módulo hermano); revisar `application: True` +
      `auto_install: True` (aparece como app suelta).
- [ ] 6.6 `l10n_ve_pos_self_order/static/src/overrides/product_list_page.xml:7,26`
      ancla el xpath en clases de presentación (`bg-view`/`border-bottom`); válido
      hoy, frágil en 19.x — preferir clases semánticas si el core las ofrece.
- [ ] 6.7 🟢 (preexistente, no del PR) `l10n_ve_accountant/models/product_template.py:86`:
      un `write` en lote sobre productos de compañías distintas lanza
      `Expected singleton` en `company[comp_field]`; procesar por-compañía.
