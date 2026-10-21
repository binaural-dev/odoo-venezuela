# Feature: identificación por cédula al iniciar una orden en el Kiosko (l10n_ve_pos_self_order)

## Why

El Kiosko nativo (`pos_self_order`) no tiene ningún flujo de identificación de cliente al **inicio** del pedido. Investigando el código (sesión previa, ver [[l10n-ve-pos-self-order-foreign-amount-fix]] para el contexto de por qué el Kiosko necesita overrides propios de `l10n_ve_pos`), el único punto donde puede aparecer un `res.partner` en el Kiosko es el popup `PresetInfoPopup` (`pos_self_order/static/src/app/components/preset_info_popup/preset_info_popup.js`), disparado desde `CartPage.pay()` — es decir, justo **antes de pagar**, no al empezar — y solo si el *preset* activo tiene `identification='address'` (`point_of_sale/static/src/app/models/pos_preset.js:28-30`). Ese formulario nativo tampoco pide `vat`/RIF en ningún caso (`pos_self_order/controllers/orders.py::validate_partner`, firma sin `vat`).

`l10n_ve_pos` fuerza `to_invoice=True` en TODAS las órdenes del PdV (requisito SENIAT — ver `static/src/overrides/models/pos_order.js:23-25`). Sin cliente identificado desde el arranque del pedido, la factura del Kiosko sale a nombre del consumidor genérico, y el negocio pidió explícitamente lo contrario: identificar al cliente por cédula **antes** de dejarlo agregar productos.

Pedido del usuario (verbatim): pantalla al iniciar la orden que pida la cédula primero; si el contacto ya existe, seguir con normalidad al catálogo; si no existe, pedir nombre, apellido, teléfono y cédula, crear el contacto, y seguir — con las direcciones precargadas desde la compañía, igual que ya hace `l10n_ve_pos` para el formulario reducido de la caja normal.

## What Changes

Todo el trabajo vive en el módulo puente `l10n_ve_pos_self_order` (ya existe — ver [[l10n-ve-pos-self-order-foreign-amount-fix]] — depende de `l10n_ve_pos` + `pos_self_order`, `auto_install=True`). No se toca `l10n_ve_pos` ni `pos_self_order` directamente.

### Reutilización obligatoria (no reinventar)

- **Búsqueda por cédula**: mismo domain que `l10n_ve_contact/models/res_partner.py::check_duplicate_vat` (línea 92): `[('prefix_vat','=',...), ('vat','=',...)]`. Cambiar `search_count` por `search(limit=1)`, sin filtro de `company_id` (mismo criterio que el helper original — `res.partner` no está scoped por compañía en este codebase).
- **Defaults de dirección desde la compañía**: `l10n_ve_pos/models/res_partner.py::default_get` (línea 30-51) + tupla `_POS_COMPANY_DEFAULT_FIELDS = (country_id, state_id, city_id, municipality, parish_id, zip)` (línea 21-28). Invocar tal cual: `self.env['res.partner'].with_context(l10n_ve_pos_partner_defaults=True).default_get(list(fields))` y mezclar el resultado en los `vals` del `create()`. Cero lógica nueva de direcciones — es exactamente el mecanismo que ya usa el formulario reducido de la caja normal.
- **Nombre**: `res.partner.name` es un único `Char` (`l10n_ve_contact`), no existe `lastname` propio. El formulario captura Nombre y Apellido en dos inputs separados mejor UX, pero se concatenan en un solo `name` al crear — no se toca el esquema del modelo.
- **Cédula**: `prefix_vat` (Selection V/E/J/G/P/C, default "V", `l10n_ve_contact/models/res_partner.py:45-58`) + `vat` (core). Reutilizar la misma selección tal cual, sin subconjunto propio.

### Cuándo se dispara

Siempre que `l10n_ve_pos_self_order` esté instalado y la caja esté en `self_ordering_mode == 'kiosk'` — **sin toggle nuevo en `pos.config`**. Mismo criterio que `to_invoice=True`: no es opcional, lo exige el negocio/SENIAT. Si algún cliente puntual no lo quiere, se desinstala el módulo puente en esa BD.

**Sin botón de "omitir"** en la primera versión — el pedido del usuario no lo menciona y sin cliente identificado la factura fiscal queda floja. Si en la prueba real hace falta un "Consumidor final / omitir", se añade en un change aparte (no inventar alcance no pedido).

### Frontend (OWL, bundle `pos_self_order.assets`)

1. Patch de `LandingPage.start()` (`pos_self_order/static/src/app/pages/landing_page/landing_page.js:97-107`): si `self_ordering_mode === 'kiosk'` y `selfOrder.currentOrder` no tiene `partner_id`, navegar a `"identification"` en vez de a `"location"`/`"product_list"` directamente. Si ya hay `partner_id` (orden en curso retomada), no interrumpir.
2. Página nueva `IdentificationPage`:
   - Paso A: selector `prefix_vat` + input numérico de cédula. Botón "Continuar" → RPC de búsqueda.
     - Encontrado → asigna `partner_id` a `selfOrder.currentOrder`, navega a `"location"` (si hay presets) o `"product_list"` (si no) — mismo criterio que ya usa `LandingPage.start()`.
     - No encontrado → muestra Paso B en la misma página, sin perder la cédula tecleada.
   - Paso B: inputs Nombre, Apellido, Teléfono (cédula ya fija del paso A). Botón "Crear y continuar" → RPC de creación → asigna `partner_id` → navega igual que el caso "encontrado".
   - Botón "Atrás" → `router.navigate("default")` (mismo patrón que `EatingLocationPage.onClickBack`).
3. Registro de ruta: `t-inherit="pos_self_order.selfOrderIndex" t-inherit-mode="extension"` añadiendo `<t t-set-slot="identification" route="...">` — mismo patrón que la ruta `"location"` (`self_order_index.xml:32-34`) — más `patch()` sobre `selfOrderIndex.components` para registrar el componente nuevo (`self_order_index.js:23-37`).

### Backend (controlador nuevo en `l10n_ve_pos_self_order`)

El módulo hoy solo tiene `models/` — se añade `controllers/`. Dos rutas públicas (`auth="public"`, `type="jsonrpc"`, mismo estilo que `pos_self_order/controllers/orders.py`), validando `access_token` con el mismo helper que usa el core (`_verify_pos_config`):

- `/l10n_ve_pos_self_order/kiosk/identify` (`access_token, prefix_vat, vat`): busca con el domain de `check_duplicate_vat`. Si existe, devuelve solo campos públicos (id, name, phone) — mismo criterio que `validate_partner` ("The endpoint doesn't return private informations").
- `/l10n_ve_pos_self_order/kiosk/identify/create` (`access_token, prefix_vat, vat, name, phone`): arma `vals` con esos campos + los defaults de dirección vía `default_get` (ver arriba), crea con `sudo()` (mismo patrón que `validate_partner`), devuelve el partner creado.

## Capabilities

### New Capabilities

- `pos-self-order-kiosk-identification`: identificación de cliente por cédula al iniciar una orden en el Kiosko, con creación de contacto y defaults de dirección desde la compañía.

## Impact

- **Módulo**: `l10n_ve_pos_self_order` — nuevos `controllers/__init__.py`, `controllers/orders.py`; nuevos `static/src/app/pages/identification_page/{identification_page.js,identification_page.xml}`, `static/src/overrides/landing_page.js`, `static/src/overrides/self_order_index.{js,xml}`; `__manifest__.py` necesita un bloque `"assets": {"pos_self_order.assets": [...]}` nuevo (el módulo hoy no declara assets, solo Python).
- **No toca** `l10n_ve_pos` ni `pos_self_order` — solo lectura/reutilización de lo que ya exponen (`check_duplicate_vat`'s domain, `default_get` con el flag de contexto existente).
- **Tests**: cobertura Python de las dos rutas nuevas (cédula encontrada, cédula no encontrada + creación, defaults de compañía aplicados correctamente) — no se ejecutan en el mismo pase que se escriben (convención ya establecida: el usuario las corre).
- **Riesgo de despliegue**: medio — es una pantalla nueva obligatoria en el camino crítico del Kiosko (nadie llega al catálogo sin pasar por ella), a diferencia de los fixes puramente backend anteriores. Probar a fondo en navegador antes de dar por bueno, especialmente: orden retomada tras recargar (no debe volver a pedir cédula si ya tiene `partner_id`), y que el patch de `LandingPage.start()` no rompa el flujo de mesas/QR en modo `mobile` (el patch debe gatear estrictamente por `self_ordering_mode === 'kiosk'`).
- **Fuera de alcance (pendiente, no corregido en este change)**:
  - Botón de "omitir identificación" — no pedido, se añade si hace falta tras la prueba real.
  - Validación de formato de cédula venezolana más allá de lo que ya valida `res.partner` a nivel de modelo (p.ej. longitud de `vat` por `prefix_vat`) — no existe hoy en el codebase, no se inventa aquí.
  - Toggle en `pos.config` para desactivar el flujo por caja — decisión consciente de NO añadirlo (ver "Cuándo se dispara" arriba); revisar si en la práctica hace falta.
  - Timing exacto de cuándo `selfOrder.currentOrder` existe como objeto local antes de llegar a `product_list` (se usa el mismo patrón que `PresetInfoPopup`, que ya asume que `currentOrder` existe como getter; confirmar en implementación si hace falta forzar su creación antes de `IdentificationPage`).

References: Tarea 78767 (Autopago POS V19), https://binaural.odoo.com/odoo/action-341/78767
