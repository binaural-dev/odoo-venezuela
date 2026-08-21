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

- [x] 3.1 🟡 `recompute_prices` — HECHO. `foreign_amount_total` se deriva de
      `sum(self.lines.mapped('price_subtotal_incl'))` (base línea-a-línea que se
      postea a la factura), no del `self.amount_total` global de `super()`. Bajo
      `round_globally` el global puede diferir un céntimo de la suma de líneas;
      así el total foráneo de cabecera queda consistente con la suma de los
      importes foráneos por línea (`line.foreign_price`, que parte de `price_unit`,
      no tiene el problema).
- [x] 3.2 🟡 `buildKioskFiscalPayload` — HECHO. `payAmount` se convierte con el
      mismo `toFiscal()` que las líneas (antes solo se redondeaba con `round_pr`,
      sin aplicar la tasa → descuadre pago≠total cuando la base ≠ VES).
- [x] 3.3 🟡 `confirmationPage` — HECHO. Guard de reentrada por `access_token`
      (`this._fiscalPrintingOrders`, un Set): si ya hay una impresión en curso
      para esa orden no se arranca otra; se limpia en el `finally`. Evita la doble
      impresión cuando el bus `PAYMENT_STATUS` reentra antes de setearse
      `mf_invoice_number`.
- [x] 3.4 🟡 Fallo de persistencia — HECHO. `_persistKioskFiscalNumber` guarda el
      número en localStorage (mapa durable por `order.id`) si el `write` falla;
      `retryPendingFiscalPersists` (en `setup`) reintenta el WRITE al arrancar (no
      reimprime); `_hydratePendingFiscalNumber` recupera el número en
      `printOrReprintKioskOrder` para que una orden pendiente reimprima COPIA en
      vez de emitir un documento nuevo. Idempotente con el guard de §1.2
      (reenviar el mismo número no re-numera).

## 4. Tests (🟡 — la deuda de mayor riesgo)

- [x] 4.1 🟡 HECHO. `tests/test_kiosk_public_routes.py`: (a) unit tests de las
      funciones puras `_ve_vat_format_error` y `_ve_within_rate_limit`; (b)
      `HttpCase` de las rutas reales: `identify` (inexistente→[]; existente NO
      devuelve `phone`, sí `has_phone`), `identify_create` (dedup no duplica; RIF
      inválido→rechaza; fill-only), `set_phone` (fill-only), `session_orders`
      (tope de `limit`; solo órdenes de la caja), `create_invoice` (orden de otra
      caja/ inexistente→rechazada), `write_mf_invoice_data` (orden ajena→rechaza;
      no sobrescribe un número distinto). El chequeo de `posted` se descartó (ver
      §1.2: escribir el número sobre un asiento posteado es el flujo normal).
- [x] 4.2 🟡 HECHO. `tests/test_deferred_invoicing.py`: fuerza el fallo
      parcheando el `_create_invoice` del core (l10n_ve_pos_mf llama a `super()`,
      la cadena llega ahí). Asserts: con `kiosk_defer_invoice` la orden queda
      `paid` + `to_invoice` sin `account_move` (savepoint revierte el `done`); vía
      `_process_saved_order` igual; la ruta explícita SÍ propaga el error.
- [x] 4.3 🟡 HECHO. Nuevo `l10n_ve_pos_mf_self_order/tests/test_mf_self_order.py`:
      `_send_payment_result` (patch de `pos.config._notify` → el payload del bus
      incluye `pos.payment` con el importe) y `_load_pos_self_data_fields` (expone
      `mf_invoice_number`/`fiscal_machine`/`mf_reportz`).
- [~] 4.4 🟡 PARCIAL. `l10n_ve_pos_mf_self_order/static/tests/unit/fiscal_payload.test.js`
      (hoot, registrado en `web.assets_unit_tests`): `buildKioskFiscalPayload` (las
      ramas de validación, conversión fiscal de líneas Y pago —§3.2—, neteo de
      descuento, `fiscal_code` strip `t`, `prefix_vat+vat`) y `normalizeProductName`.
      PENDIENTE: `kiosk_sync_queue.js` (la clasificación vive dentro de un `patch`
      de `SelfOrder` con IndexedDB+rpc; testearla aislada exige mockear ese
      entorno — es de nivel integración, se deja anotado).
- [x] 4.5 🟡 HECHO. `l10n_ve_accountant/tests/test_product_template.py`
      (`test_04c...`): rama `not tax_ids` del lado VENTA multi-compañía (impuesto
      de venta SOLO de otra compañía → conserva el ajeno + agrega el default
      propio); fija `account_sale_tax_id` de `base.main_company` en el test
      (hermético); assert de "no error".
- [x] 4.6 🟡 HECHO. `tests/test_res_partner_pos_self_data.py`: `TransactionCase`
      que verifica que `_load_pos_self_data_read` inyecta `vat`/`prefix_vat`
      (contrato de Megasoft), preserva `id`/`name` del core, y recordset vacío→[].

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
