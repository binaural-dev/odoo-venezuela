# Feature: ajustes al módulo de Kiosko (Tarea 80343)

## Why

La tarea 80343 pide un conjunto de ajustes de UX/negocio al Kiosko
(`pos_self_order` en modo `kiosk`) que hoy tiene huecos frente a lo que el
cliente necesita en Venezuela:

1. El popup nativo de cancelar orden está en inglés y sin criterio de
   traducción propio del módulo.
2. Los pasos de creación de contacto no avisan cuáles campos son
   obligatorios.
3. El teléfono del cliente se pide como texto libre, sin validar operadora ni
   formato — datos sucios que llegan a facturación.
4. La dirección del cliente (estado/municipio/calle) no se recoge en el
   Kiosko, aunque el negocio a veces la necesita para delivery/facturación.
5. La pantalla de pago no muestra ningún monto (base imponible, impuestos,
   total) — el cliente paga a ciegas.
6. El total en moneda foránea (Bs. estable / USD) tampoco se muestra: los
   helpers que lo calculan en caja (patches de modelo de `l10n_ve_pos`) no
   están incluidos en el bundle del Kiosko.
7. No hay teclado en pantalla para los campos de texto (nombre, apellido,
   teléfono); el Kiosko depende del teclado nativo del sistema operativo, que
   en muchos terminales no aparece.

## What Changes

Todos los cambios viven en `l10n_ve_pos_self_order` (UX del Kiosko sobre
`pos_self_order`), son aditivos/opcionales donde el negocio lo pide, y no
tocan el flujo QR/móvil salvo que se indique lo contrario.

1. **Popup de cancelar orden** (`CancelPopup`, core `pos_self_order`):
   `t-inherit` con el texto "¿Desea cancelar la orden?" y botones "Sí"/"No"
   (mismo patrón que `confirmation_page.xml`).
2. **Leyenda de campos obligatorios**: "LOS CAMPOS MARCADOS CON * SON
   OBLIGATORIOS" en los pasos de teléfono/creación de contacto de
   `IdentificationPage`; el "*" se agrega fuera del término traducible.
3. **Teléfono obligatorio y validado**: selector de operadora venezolana
   (0412/0414/0416/0422/0424/0426) + número de exactamente 7 dígitos.
   Se guarda como `"0414-1234567"`. Validado en cliente y espejado en
   servidor (`controllers/orders.py`) para `identify/create` y `set_phone`.
4. **Dirección opcional/obligatoria por configuración**: nuevo booleano
   `pos.config.self_ordering_require_address` (mismo patrón que
   `self_ordering_hide_catalog`); cuando está activo, el paso de creación de
   contacto exige Estado + Municipio (desplegables, `res.country.state` /
   `res.country.municipality` de `l10n_ve_location`) y Calle (texto), con
   la misma validación espejada en servidor.
5. **Resumen de montos antes de pagar** (pie de `CartPage`, o bajo el
   resumen de líneas en modo solo escaneo): base imponible, desglose de
   impuestos por tasa y total en Bs., más el total en moneda foránea (misma
   tasa operativa que usa `l10n_ve_pos` en caja) cuando la compañía tiene
   moneda foránea configurada. El total foráneo NO se reimplementa: el
   manifest agrega `l10n_ve_pos/static/src/overrides/models/*` (patches puros
   de modelo) a `pos_self_order.assets` y el componente usa
   `get_foreign_total_with_tax()`, con la misma conversión y redondeo que la
   caja. No va en `PaymentPage`: con un único método Megasoft (lo
   recomendado) el core lo auto-selecciona y el VPOS abre de inmediato, y
   ese salto directo se conserva.
6. **Teclado en pantalla** (`KioskKeyboard`, componente OWL propio, sin
   librerías externas): QWERTY + Ñ + números + espacio + borrar + mayúsculas,
   con modo numérico para teléfono/cédula. Se muestra al enfocar los campos
   de texto de `IdentificationPage` y escribe en el campo activo. Reusa el
   estilo del numpad propio (`o_ve_numpad`).

## Capabilities

### Added Capabilities

- `pos-self-order-kiosk-cancel-popup`: texto y botones del popup de cancelar
  orden del Kiosko en español.
- `pos-self-order-kiosk-required-fields-legend`: leyenda de campos
  obligatorios en los pasos de contacto del Kiosko.
- `pos-self-order-kiosk-phone-required`: teléfono venezolano obligatorio y
  validado (cliente + servidor).
- `pos-self-order-kiosk-address`: dirección opcional/obligatoria por
  configuración en la creación de contacto del Kiosko.
- `pos-self-order-kiosk-payment-summary`: resumen de montos (base, impuestos,
  total local y foráneo) del Kiosko antes de pagar.
- `pos-self-order-kiosk-keyboard`: teclado en pantalla para los campos de
  texto del Kiosko.

## Impact

- **Módulo**: `l10n_ve_pos_self_order` únicamente (no toca `integra-addons` ni
  el core `pos_self_order`/`point_of_sale`, salvo por herencia/`patch()`).
- **Backend**: `models/pos_config.py`, `models/res_config_settings.py`,
  `models/res_country_municipality.py` (nuevo), `controllers/orders.py`,
  `views/res_config_settings_views.xml`.
- **Frontend** (bundle `pos_self_order.assets`):
  `static/src/overrides/cancel_popup.xml` (nuevo),
  `static/src/app/components/kiosk_amounts_summary/kiosk_amounts_summary.{js,xml}`
  (nuevo), `static/src/overrides/product_list_page.xml`,
  `static/src/app/pages/identification_page/identification_page.{js,xml,scss}`,
  `static/src/app/components/kiosk_keyboard/kiosk_keyboard.{js,xml,scss}`
  (nuevo).
- **i18n**: `i18n/es_VE.po` (todas las cadenas nuevas en inglés + traducción
  `es_VE`).
- **Compatibilidad**: `binaural_megasoft_self_order` sigue funcionando sin
  cambios (este change ya no toca `PaymentPage`).
- **Riesgo**: medio — toca la pantalla de identificación (ya usada en
  producción) y el carrito; cambios detrás de validación explícita y, donde
  aplica, detrás de un flag de configuración.

References:
- Tarea: https://binaural.odoo.com/odoo/action-341/80343
