# Migration Lessons: l10n_ve_pos Odoo 17 → 19

## API renames (canonical mapping)

| v17 | O19 | Dónde aplica |
|-----|-----|-------------|
| `Order` | `PosOrder` | `@point_of_sale/app/models/pos_order` |
| `Payment` | `PosPayment` | `@point_of_sale/app/models/pos_payment` |
| `usePos` | `usePos` (same name) | `@point_of_sale/app/hooks/pos_hook` (not `app/store/pos_hook`) |
| `get_paymentlines()` | `payment_ids` (getter) | `Array.from(this.payment_ids \|\| [])` |
| `get_total_with_tax()` | `totalDue` (getter) | `Number(this.totalDue ?? 0) \|\| 0` |
| `get_due()` | `remainingDue` (getter) | `Number(this.remainingDue ?? 0) \|\| 0` |
| `add_paymentline(method)` | `addPaymentline(method)` | camelCase rename |
| `select_paymentline(line)` | `selectPaymentline(line)` | camelCase rename |
| `assert_editable()` | `assertEditable()` | camelCase rename |
| `electronic_payment_in_progress()` | `electronicPaymentInProgress()` | camelCase rename |
| `selected_paymentline` | `selectedPaymentLine` | camelCase rename |
| `payment.cid` | `payment.uuid` | property rename |
| `payment.payment_method` | `payment.payment_method_id` | `payment_method` is `undefined` → always use `payment_method_id` with `?.` |
| `new Payment(env, opts)` | `this.models["pos.payment"].create({pos_order_id: this, ...})` | O19 registry pattern |
| `this.paymentlines.add(line)` | auto via `pos_order_id` in create | no manual add needed |
| `formatCurrency(amt, 'Product Price')` | `formatCurrency(amt)` | O19 accepts only value, no format type |
| `Payment.prototype` | `PosPayment.prototype` | import + patch target |
| `Order.prototype` | `PosOrder.prototype` | import + patch target |

## CRITICAL: NO usar `this.pos` en PosOrder

**En Odoo 17**, `this.pos` estaba disponible en el `setup()` del PosOrder. **En Odoo 19, NO.** El core no asigna `this.pos` al PosOrder.

**En Odoo 19**, el PosOrder obtiene el contexto a través de getters nativos:

```js
// En lugar de this.pos.currency.rounding:
this.currency.rounding      // → this.config.currency_id.rounding

// En lugar de this.pos.config.XXXX:
this.config.XXXX             // → this.models["pos.config"].getFirst().XXXX

// En lugar de this.pos.currency.rounding en compute_igtf_amount:
this.currency.rounding
this.config.igtf_percentage
```

**`this.currency`** es un getter del core PosOrder que retorna `this.config.currency_id`.

**`this.config`** es un getter del core PosOrder que retorna `this.models["pos.config"].getFirst()`.

Ambos están disponibles en `setup()` porque el core los setea vía `this.config_id = this.config` o desde `vals.json`.

**Excepción**: en `PaymentScreen` y `PaymentScreenStatus` (componentes OWL), `this.pos` se obtiene vía `usePos()` hook. Ahí SÍ está disponible.

## Silent-trap: `?.() || 0`

El patrón `x?.method?.() || 0` es peligroso en migraciones donde métodos se convirtieron en getters:
- Si `method` fue renombrado a getter, `x.method` es `undefined`
- `undefined?.()` retorna `undefined`
- `undefined || 0` retorna `0`
- **El código nunca falla, solo devuelve 0**

**Patrón defensivo recomendado**:
```js
const value = Number(
  this.totalDue ??
  (typeof this.get_total_with_tax === "function" ? this.get_total_with_tax() : 0)
) || 0;
```

## `update_igtf()` timing

En O17, `update_igtf()` se llamaba en `setup()` y `this.pos` ya existía. En O19, si se usa `this.currency`/`this.config` en vez de `this.pos`, se puede seguir llamando en `setup()` sin problemas.

## OWL QWeb templates

- Los templates OWL con `t-inherit-mode="extension"` y `owl="1"` se cargan como parte del asset bundle JS, NO como vistas en `ir.ui.view`
- Las XPath expressions se evalúan contra el template BASE (el del core), que se compila y cachea en el JS
- `hasclass('classname')` es la forma correcta de filtrar por clase
- Para verificar que un XPath funciona, hay que leer el template nativo O19 dentro del contenedor Docker

## Bundle caching

Cuando se modifican archivos JS o XML de OWL templates:
1. El módulo debe actualizarse (`-u modulo` o UI Upgrade)
2. Los assets se regeneran con nuevo hash
3. Si el hash no cambia, es porque Odoo no encontró cambios en los archivos
4. Verificar que el archivo modificado está en el directorio correcto que el contenedor está montando

## Foreign due/change: derivar del LOCAL, no de foreign_amount (2026-07-09)

`get_foreign_due()` y `get_foreign_change()` se calculan como UNA conversión
de su contraparte local (`localToForeign(remainingDue)` /
`localToForeign(-sign * change)`), NO como `total foráneo - pagado foráneo`.
Motivo: `get_foreign_total_paid()` suma `line.foreign_amount`, que es 0 en
métodos locales (`_recomputeForeignFromLocal`), así que un pago en Bs nunca
reducía el "restante alterno". `remainingDue`/`change` (core) descuentan
TODOS los pagos vía `amountPaid`, y si otro módulo (l10n_ve_pos_igtf) los
parchea, el panel foráneo lo refleja sin que este módulo lo conozca.

## Pendientes por tratar (2026-07-10) — RESUELTO 2026-07-21

### foreign_amount = 0 en líneas de métodos locales — NO debería pasar

`_recomputeForeignFromLocal` (static/src/overrides/models/payment_model.js)
fijaba `foreign_amount = 0` cuando el método no era `is_foreign_currency`.
Jesús: eso no debería pasar; la línea en Bs debería llevar su equivalente
foráneo (`localToForeign(amount)`).

NO era meramente visual — consumidores de `pos.payment.foreign_amount` con 0:

1. `models/pos_payment.py::_create_payment_moves` (y el de l10n_ve_pos_igtf):
   `foreign_debit`/`foreign_credit` de los apuntes quedaban en 0 para pagos
   en Bs → la contabilidad dual foránea no registraba esos pagos.
2. `report/report_saledetails.py` y `report/payment_report_pos.py`:
   `sum(foreign_amount)` por método de pago en SQL/Python → f_total = 0
   para métodos locales en los reportes.
3. Frontend: `get_foreign_total_paid()` no veía pagos locales (ya
   desacoplado de due/change el 2026-07-09), ni `get_foreign_amount()`
   (usado en `payment_line.xml` para el monto foráneo junto a cada línea).
4. **`models/pos_session.py` — el mayor consumidor, no listado en la nota
   original.** Todo el cierre de sesión (`_accumulate_amounts`,
   `_create_bank_payment_moves`, `_create_split_account_payment`,
   `_create_combine_account_payment`, `_create_invoice_receivable_lines`,
   `_create_cash_statement_lines_and_cash_move_lines`) lee
   `payment.foreign_amount` sin gate por `is_foreign_currency` — con el
   valor en 0, TODAS las líneas de recibo de cierre de sesión para
   métodos locales quedaban en `foreign_debit`/`foreign_credit = 0`. Este
   es el mecanismo real detrás de los casos encontrados en las sesiones
   Binaural C.A/00043 y /00044 (ver openspec/changes/
   `l10n-ve-pos-session-close-cash-foreign-amount-fix`, que arregló un
   bug de escritura DISTINTO — el de ahí ya no se saltaba la escritura,
   pero escribía el valor de origen equivocado por esto).

**Fix aplicado**: `_recomputeForeignFromLocal` ya no filtra por
`is_foreign_currency` — siempre calcula `order.localToForeign(amount)`.
Se eliminó `_isForeignMethod()` (quedó sin uso). Auditoría de los 4
consumidores de arriba + `l10n_ve_pos_igtf/pos_payment.py::_create_payment_moves`
(agente Explore, 2026-07-21): ninguno hace resta/división que asuma 0 —
todo es asignación directa sobre líneas ya identificadas por importe, sin
riesgo de doble conteo. Se encontró además un bug latente que este cambio
arregla de paso: en `l10n_ve_pos_igtf`, un método local con
`apply_igtf=True` calculaba mal `amount_without_igtf` porque
`foreign_amount` era 0 pero `foreign_igtf_amount` (independiente) sí
estaba poblado. Ningún test (Python ni JS) dependía de la invariante
vieja — se agregó cobertura nueva en `payment_model.test.js`
(`_recomputeForeignFromLocal` para método local vs. foráneo).

**Pendiente aparte, no cubierto por este fix**: data-fix de los asientos
YA generados con el valor viejo (0) en las sesiones 00043 y 00044.

## Pendientes por tratar (2026-07-21)

### Error "El registro no existe o fue eliminado" al recargar/abrir el PdV en otra pestaña (multi-tab race en opening_control)

Reproducido en `pos` (config_id 6, "Prueba de Entrada"): con el PdV abierto
en la pantalla de "Control de apertura" en una pestaña, al recargarla o al
intentar abrir el mismo PdV desde OTRA pestaña, aparece:

```
Ocurrió un error al cargar el punto de venta:
El registro no existe o fue eliminado.
(Registro: pos.session(103,), Usuario: 2)
```

Confirmado en BD: la sesión `pos.session(103,)` ya no existía cuando se
disparó el error (hueco en la secuencia de ids entre una sesión 101 cerrada
normalmente y una 104 en `opening_control`, sin que 102/103 quedaran en la
tabla). O sea: la pestaña que mostraba el error tenía cacheado (cliente,
IndexedDB/localStorage del PdV offline-first) el id de una sesión que ya
fue borrada/superada del lado servidor — y el RPC de recarga no maneja ese
caso, lanza el error crudo en vez de recuperarse (ej. re-derivar
`current_session_id` y redirigir).

**Pista para investigar** (no confirmado, solo lectura de código nativo,
no reproducido paso a paso con logging):
`pos.config.current_session_id` (`_compute_current_session`,
`point_of_sale/models/pos_config.py:344`) se resuelve por CONFIG, no por
usuario/pestaña — toma la sesión no-cerrada de mayor id
(`session[0]`, "ordered by id desc"). Si dos pestañas de la misma sesión de
navegador (mismo `Usuario: 2`) disparan cada una la creación de una sesión
`opening_control` para el mismo config casi al mismo tiempo (carrera al
abrir el PdV, o al recargar antes de que la pestaña vieja re-consulte
`current_session_id`), puede terminar existiendo más de una sesión
`opening_control` para el mismo config simultáneamente; alguna lógica de
limpieza (candidatos: `_unrelevant_records`, referenciado en
`pos_session.py:196` pero no definido en ese archivo — rastrear su mixin/
definición real; o el propio flujo de `open_ui`/`_action_to_open_ui` en
`pos_config.py`) termina borrando la sesión "perdedora" de la carrera. La
pestaña que ya tenía esa sesión perdedora cargada no se entera y falla al
volver a pedirla.

Contexto: se disparó justo después de limpiar manualmente sesiones
abandonadas en `opening_control` vía `delete_opening_control_session()`
(ver `point_of_sale/models/pos_session.py:201`) desde el shell, con el
usuario probando el PdV en paralelo en el navegador — pero también volvió
a ocurrir sin intervención manual, solo con dos pestañas normales, así que
no depende de que alguien borre sesiones por SQL/shell.

**No corregido en este pase** — queda para sesión aparte. Si se aborda:
revisar si el fix va del lado servidor (no permitir/objetar sesiones
`opening_control` duplicadas por config antes de que una pestaña llegue a
depender de la perdedora) o del lado cliente (manejar el error de "record
does not exist" en la carga de sesión re-derivando `current_session_id` en
vez de mostrar el diálogo crudo).

#### Actualización (2026-07-22): reproducido también al confirmar el control de apertura, no solo al recargar

Confirmado por el usuario: el mismo error también aparece a veces al pulsar
"confirmar"/pasar la pantalla de control de apertura (no únicamente al
recargar una pestaña vieja). Sigue sin reproducirse paso a paso con logging,
pero la lectura de código (nativo `point_of_sale`, sin overrides de
`l10n_ve_pos` en ninguno de estos archivos — confirmado con grep) descarta
la pista anterior y aporta dos hallazgos concretos:

1. **La pista de `_unrelevant_records` era un callejón sin salida.** Su
   única definición es la del mixin genérico
   (`point_of_sale/models/pos_load_mixin.py:58`): solo marca como
   "irrelevante" un registro si `not record.active` (o si no hay acceso de
   lectura). `pos.session` no la sobreescribe. No borra sesiones duplicadas
   ni tiene relación con `opening_control`; solo la usa
   `filter_local_data` (`pos_session.py:190`) para decirle al cliente qué
   purgar de IndexedDB. Descartar como mecanismo de limpieza.

2. **Ya existe una mitigación server-side para el caso "sin sesión activa
   todavía"**: `PosController.pos_web`
   (`point_of_sale/controllers/main.py:82-90`) toma un lock de fila
   `SELECT ... FOR UPDATE NOWAIT` sobre `pos_config` antes de llamar a
   `open_ui()` precisamente para evitar que dos pestañas creen sesiones
   duplicadas al abrir. Pero esto solo aplica cuando
   `not pos_config.has_active_session`; en cuanto existe una sesión en
   `opening_control` (ya no cerrada), esa rama se salta por completo —
   ambas pestañas simplemente reutilizan la misma sesión vía el `search()`
   de la línea 66/77. O sea: el lock no cubre el caso reportado (sesión
   `opening_control` ya existente, recarga o confirmación posterior).

3. **Hay dos manejos de error distintos y NO equivalentes en el cliente**:
   - `opening_control_popup.js:39-57` (`confirm()`, llamada a
     `set_opening_control`) SÍ tiene recuperación: si el RPC devuelve
     `MissingError` y `this.pos.isSessionDeleted()`
     (`pos_store.js:3042`, un `searchCount` fresco por id) confirma que la
     sesión ya no existe, hace `window.location.reload()` en vez de
     mostrar el error crudo.
   - `data_service.js` → `loadInitialData()` (rededor de líneas 296-366,
     la llamada a `pos.session.load_data(odoo.pos_session_id, ...)` que
     corre en **toda** carga/recarga de página) **NO tiene ninguna
     recuperación**: cualquier error ahí (catch en línea 357-364) termina
     en `window.alert(message)` con el mensaje crudo — que es exactamente
     el texto "Ocurrió un error al cargar el punto de venta..." reportado.
     Este es el candidato más fuerte para el mensaje visto al recargar.

**Pendiente de precisar**: al confirmar (no recargar) el error debería pasar
por `opening_control_popup.js`, que ya sabe recuperarse — así que si ahí
también se ve el diálogo crudo, falta confirmar con la pestaña Network del
navegador si el RPC que falla es realmente `set_opening_control` (y por qué
`isSessionDeleted()` no habría detectado el caso) o si en realidad es un
`load_data`/`filter_local_data` disparado en paralelo (p.ej. por un
`bus`/heartbeat) que cae en la rama sin recuperación de `data_service.js`.

#### Causa raíz confirmada (2026-07-22): race en el beacon de limpieza `beforeunload`

El usuario confirmó que el error **también aparece con un F5 real** (no solo
con recarga interna de la SPA), lo cual descartaba la teoría del service
worker sirviendo caché vieja (`service_worker.js:7-16` es "network-first":
intenta la red real primero, solo cae al caché si la conexión falla — no
aplica aquí porque el servidor sí responde).

Se cruzó `docker logs proj` (contenedor Odoo, `--since 3h`) con la tabla
`pos_session` de la BD `pos` (`proj_db`) justo después de una reproducción
real del usuario, y aparece el mecanismo completo:

```
19:53:59  POST .../pos.session.delete_opening_control_session   (x2-3, casi simultáneas)
19:54:15  POST .../pos.session.delete_opening_control_session
19:54:15  WARNING: El registro no existe o fue eliminado. (Registro: pos.session(119,), Usuario: 2)
          — en load_data_params, load_data y write, las tres para pos.session(119,)
19:54:32  POST .../pos.session.delete_opening_control_session
```

Verificado en BD: `pos_session` salta de `117` (closed) a `120` (opened) —
`118` y `119` no existen. Como el cliente sí llegó a referenciar el id 119
en tres llamadas distintas, la sesión existió de verdad y fue borrada
(`unlink`), no es un hueco de secuencia por rollback.

**Mecanismo, ubicado en `point_of_sale/static/src/app/main.js:45-71`**:

```js
window.addEventListener("beforeunload", function (event) {
    ...
    if (pos?.session?.state === "opening_control") {
        browser.sessionStorage.setItem("pos_reload_recovery", String(pos.session.id));
        navigator.sendBeacon("/web/dataset/call_kw", /* delete_opening_control_session */);
    }
});
```

Cada vez que se recarga o cierra una pestaña que está en la pantalla de
control de apertura, el cliente dispara un `sendBeacon` (fire-and-forget,
sin esperar respuesta ni garantía de orden) que borra esa misma sesión
`opening_control`, y guarda un flag en `sessionStorage` para que la
siguiente carga, si ve el mismo `pos_session_id`, fuerce un
`window.location.reload()` extra (`main.js:33-38`) — un intento de
autocorrección para el caso de una sola pestaña.

El problema: `pos_web()` (`controllers/main.py:66-77`) resuelve la sesión
`opening_control` **por config, no por pestaña/usuario** — así que si hay
dos pestañas abiertas sobre el mismo PdV (config 6, "Prueba de Entrada"),
**ambas comparten el mismo `pos.session` id** mientras está en control de
apertura. Si una pestaña se recarga o se cierra, su beacon borra esa sesión
compartida; la otra pestaña (o la misma, en su propio ciclo de arranque)
puede tener en vuelo `load_data_params` / `load_data` / `write` sobre ese
mismo id justo cuando el beacon aterriza en el servidor — de ahí el
`MissingError` en las tres llamadas casi seguidas del log. El F5 no
"soluciona" nada porque el propio F5 es el que dispara el beacon que causa
el borrado.

Esto explica ambos síntomas reportados con un solo mecanismo: (a) al
recargar, porque recargar ES el disparador del beacon; (b) al confirmar el
control de apertura, si la otra pestaña se recargó/cerró justo antes y ya
borró la sesión que la primera estaba a punto de confirmar (aunque este
caso sí debería intentar recuperarse vía `isSessionDeleted()` en
`opening_control_popup.js` — pendiente confirmar si esa recuperación llega
a tiempo o si el `MissingError` la esquiva).

**No es una regresión de `l10n_ve_pos`** (ninguno de `main.js`,
`pos_store.js`, `data_service.js`, `pos_config.py`/`pos_session.py` está
parcheado por el módulo — confirmado con grep) y tampoco requiere el bypass
de los tests de carga (`onboarding_creation` en
`tests/perf/users/odoo_mixin.py`) ni el `workers=8` de este entorno como
explicación principal — aunque ambos siguen siendo factores que aumentan la
probabilidad de pisar la ventana de la carrera en este deployment frente a
un runbot de un solo tester.

**Fix propuesto (no implementado)**: `pos_web()` no debería reutilizar una
sesión `opening_control` ajena a la pestaña que la solicita sin más
salvaguarda, o el beacon de `beforeunload` debería no borrar la sesión si
hay otra pestaña con la misma sesión aún activa (p. ej. contando pestañas
vía `BroadcastChannel`/`localStorage` antes de mandar el `sendBeacon`).
Alternativa más simple del lado servidor: que `delete_opening_control_session`
verifique que no haya otra actividad reciente sobre esa sesión (heartbeat)
antes de borrarla.

## PartnerDetailsEdit desapareció: el PdV edita res.partner con la vista form real del backoffice (2026-07-25)

En Odoo 17, `l10n_ve_pos` reescribía a mano el editor de clientes del PdV
(`static/src/overrides/screens/partner_editor/{partner_editor.js,partner_editor.xml}`,
eliminado en la migración por los commits `cc8e92216` y `a4131fe8b`). La
tentación al portar esa personalización a Odoo 19 es buscar el componente
OWL equivalente y parchearlo — pero **`PartnerDetailsEdit` ya no existe**.

En Odoo 19, `PosStore.editPartner()`
(`addons/point_of_sale/static/src/app/services/pos_store.js:2307-2318`)
abre la acción `point_of_sale.res_partner_action_edit_pos`
(`target="new"`) envuelta en `makeActionAwaitable`, y esa acción apunta
`view_id` a `base.view_partner_form` — la vista form **real** del
backoffice, renderizada dentro de un diálogo. No hay editor OWL propio
que parchear: el formulario del PdV es un espejo literal del de
Contactos. El mismo patrón se repite para productos
(`product_template_action_edit_pos`, `pos_store.js:2326`) y es
previsible que aplique también a otras entidades editables desde el PdV
en versiones futuras (ej. órdenes).

**Corolario práctico**: para personalizar SOLO el formulario del PdV
(sin tocar el backoffice) no se patchea OWL ni se reimplementa un editor
— se crea una vista derivada `mode="primary"` (no herencia en modo
extensión, que sí modificaría el arch compartido) sobre la vista base
correspondiente, y se sobreescribe el `view_id` de la acción
`*_action_edit_pos` para que apunte a esa vista reducida. `view_id` es
`ondelete='set null'`
(`odoo/addons/base/models/ir_actions.py:308`), así que desinstalar el
módulo deja la acción funcionando con la vista por defecto, sin romper
nada.

Para inyectar contexto (p. ej. valores por defecto) hacia esa vista, hay
dos puntos de extensión:

- El campo `context` de la propia acción `*_action_edit_pos`
  (declarativo, sirve para flags simples).
- `PosStore.editPartnerContext(partner)`
  (`pos_store.js:2301`, devuelve `{}` por defecto) — pero ojo:
  `editPartner()` lo invoca **sin pasarle el argumento `partner`**
  (`pos_store.js:2313`: `this.editPartnerContext()`, no
  `this.editPartnerContext(partner)`), así que dentro del hook siempre
  llega `undefined` y no sirve para distinguir "editar existente" de
  "crear nuevo" sin leer otro estado del store.

Usado en `openspec/changes/l10n-ve-pos-partner-quick-form-company-defaults/`:
vista `l10n_ve_pos.view_partner_form_pos` (`mode="primary"`,
`priority=100`) + `context = {'l10n_ve_pos_partner_defaults': True}` en
la acción + `default_get` server-side que lee ese flag — ver `design.md`
de ese change para el detalle de por qué se eligió `context` de la
acción sobre `editPartnerContext()` y `default_get` sobre `default_*`
en el contexto.

## Lo comentado no se borra sin inventariar qué hacía (2026-07-26)

Al limpiar los 7 ficheros de override del PdV que estaban 100% comentados
o vacíos (change `l10n-ve-pos-dead-override-files-cleanup`), se documentó
antes qué característica tenía cada uno y en qué estado está hoy, porque en
esta migración ha ocurrido varias veces que algo comentado terminó
haciendo falta.

**El inventario completo está en**
`openspec/changes/archive/*-l10n-ve-pos-dead-override-files-cleanup/removed-features.md`,
con el comando `git show` para recuperar cada fichero y el estado de cada
característica (MIGRADA / SUPERADA / NO MIGRADA).

Dos hallazgos de ese inventario que **no** son sólo documentación:

1. **La validación de existencias al enviar la orden no está operativa en
   V19.** El `pos_model.js` comentado tenía `update_products()` +
   `push_orders`/`push_single_order`, que refrescaban el stock de los
   productos de la orden antes de enviarla (con la API V17
   `pos.session.get_pos_ui_product_product_by_params`, inexistente en
   V19). Consecuencia: los controladores `/validate_products_order`
   (`controllers/controller.py:13`) y `/validate_products_in_warehouse`
   (`controllers/controller.py:39`) siguen definidos en Python pero **no
   tienen ningún llamador en todo `src/`**. Lo que sí quedó vivo es algo
   más simple: ocultar del catálogo los productos sin stock
   (`product_screen.js:77`) y mostrar la cantidad libre en la ficha
   (`product_card.js:48-52`). Si el negocio necesita el bloqueo al
   pagar/enviar, hay que portar esa parte.

2. **Había un `compute_all` custom (~200 líneas) y su delta contra el core
   se ha perdido de vista.** Era una copia del motor de cálculo de
   impuestos nativo de V17 (los comentarios numerados son literales del
   core) sin ninguna referencia a moneda foránea, IGTF ni tasa, así que la
   modificación local no está documentada en ninguna parte. Si aparece un
   descuadre de impuestos en el PdV, el primer paso es diffear ese cuerpo
   (`git show 8768f65d7^:l10n_ve_pos/static/src/overrides/models/pos_model.js`)
   contra el `compute_all` de Odoo 17 para aislar el delta antes de portar
   nada.

Regla práctica: cuando se retire un override comentado, dejar la anotación
de qué hacía y en qué estado queda (migrada / superada / no migrada) en el
change que lo retira. Borrar el fichero está bien; borrar la memoria de la
característica, no.

## Pendientes por tratar (2026-07-26)

Consolidado de lo que quedó abierto tras el formulario de contacto del PdV y
la limpieza de overrides muertos. Los dos changes están archivados, así que
sus `tasks.md` ya no salen en `openspec list`: esta lista es el índice.

1. **Validación de existencias al enviar la orden — NO MIGRADA.** Los
   controladores `/validate_products_order` (`controllers/controller.py:13`) y
   `/validate_products_in_warehouse` (`controllers/controller.py:39`) siguen
   definidos sin ningún llamador en `src/`; su único consumidor era el
   `update_products()` del `pos_model.js` comentado (API V17
   `pos.session.get_pos_ui_product_product_by_params`). Decidir: portar a la
   API de datos de V19 o eliminar los controladores. Riesgo de negocio:
   vender sin stock. Detalle en
   `changes/archive/2026-07-26-l10n-ve-pos-dead-override-files-cleanup/removed-features.md`.
2. **`compute_all` custom — delta no documentado.** Copia del motor de
   impuestos de Odoo 17 sin referencias a moneda foránea/IGTF. Si aparece un
   descuadre de impuestos en el PdV, diffear
   `git show 8768f65d7^:l10n_ve_pos/static/src/overrides/models/pos_model.js`
   contra el `compute_all` nativo de V17 antes de portar nada.
3. **RIF junto al nombre del cliente en el actionpad — NO MIGRADA.** Lo hacía
   `actionpad_widget.xml` (`(prefix_vat + vat)` tras el nombre). `prefix_vat`
   ya viaja al frontend (`models/res_partner.py`), solo falta la plantilla
   contra el componente V19 equivalente. Es el pendiente más barato.
4. **Atajo de Enter en el buscador de clientes — NO MIGRADA.** Lo hacía
   `partner_list.js`: Enter sin resultados abría la creación de cliente con
   el texto buscado como RIF.
5. **Validaciones del contacto del PdV no reimplantadas.** El editor V17
   exigía RIF, teléfono `/^0[24]\d{9}$/`, calle y país. Hoy solo hay los
   `required` de vista de `l10n_ve_contact` / `l10n_ve_location`. Ligado a
   ello, `pos.config.validate_phone_in_pos` (`models/pos_config.py:37`) es un
   campo huérfano: sin consumidor ni vista. Implementar la validación o
   eliminar el campo.
6. **`res.company.pos_show_free_qty_on_warehouse` huérfano.**
   `models/res_company.py:12`, con related en `pos.config` y bloque en los
   ajustes (`views/res_config_settings.xml:146-154`), pero ningún lector en
   Python ni en JS.
7. **Globs redundantes de assets** en `__manifest__.py:38-41`
   (`static/src/**/**`, `static/src/**/**/**/*` y la ruta explícita de
   `payment_model.js` describen el mismo conjunto).
8. **Sin cobertura de tests** del formulario reducido del PdV ni de su
   `default_get` (no se escribieron por indicación expresa del usuario).
