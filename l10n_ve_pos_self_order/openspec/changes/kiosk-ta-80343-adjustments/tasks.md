# Tasks

## 1. Popup de cancelar orden (punto 5)

- [x] 1.1 `static/src/overrides/cancel_popup.xml`: `t-inherit` de
      `pos_self_order.CancelPopup` — "¿Desea cancelar la orden?" / "Sí" / "No"
- [x] 1.2 `i18n/es_VE.po`: cadenas nuevas
- [x] 1.3 `__manifest__.py`: bump de versión (1.3 → 1.4)

## 2. Leyenda de campos obligatorios (punto 3)

- [x] 2.1 `identification_page.js`: getter `requiredFieldsLegend`
- [x] 2.2 `identification_page.xml`: mostrar la leyenda en los pasos de
      teléfono y creación de contacto
- [x] 2.3 `i18n/es_VE.po`: cadena nueva

## 3. Teléfono obligatorio y validado (punto 1)

- [x] 3.1 `identification_page.js`: selector de operadora (0412/0414/0416/
      0422/0424/0426) + número de 7 dígitos, formato `"0414-1234567"`
- [x] 3.2 `identification_page.xml`: reemplazar el input libre de teléfono por
      el selector + número, en los pasos de teléfono y creación de contacto
- [x] 3.3 `identification_page.scss`: estilo del selector de operadora
- [x] 3.4 `controllers/orders.py`: `_ve_phone_format_error` — mismo patrón que
      `_ve_vat_format_error`; aplicado en `identify_create` y `set_phone`
- [x] 3.5 `i18n/es_VE.po`: cadenas nuevas (JS + Python)
- [x] 3.6 `tests/test_kiosk_public_routes.py`: tests de formato de teléfono

## 4. Dirección opcional/obligatoria (punto 2)

- [x] 4.1 `models/res_country_municipality.py` (nuevo): `pos.load.mixin` sobre
      `res.country.municipality` para exponerlo al Kiosko
- [x] 4.2 `models/pos_config.py`: `self_ordering_require_address` (Boolean) +
      `_load_self_data_models` (agrega `res.country.municipality`) +
      `_load_pos_self_data_fields` (expone el flag)
- [x] 4.3 `models/res_config_settings.py`: related
      `pos_self_ordering_require_address`
- [x] 4.4 `views/res_config_settings_views.xml`: `<setting>` nuevo
- [x] 4.5 `controllers/orders.py`: `_ve_address_format_error`; nuevos
      parámetros `state_id`/`municipality_id`/`street` en `identify_create`
      (incluye cruce estado↔municipio server-side)
- [x] 4.6 `identification_page.js`: estado + validación de estado/municipio/
      calle; municipios filtrados por estado elegido
- [x] 4.7 `identification_page.xml`: desplegables de Estado/Municipio + campo
      Calle en el paso de creación de contacto
- [x] 4.8 `__manifest__.py`: dependencia explícita de `l10n_ve_location`
- [x] 4.9 `i18n/es_VE.po`: cadenas nuevas
- [x] 4.10 `tests/test_kiosk_public_routes.py`: tests de dirección obligatoria/
      opcional, cruce estado↔municipio y de datos expuestos
      (`res.country.municipality`, flags de `pos.config`)

## 5. Resumen de montos en pago (puntos 7+8)

- [x] 5.1 `models/pos_config.py`: exponer `foreign_currency_id`/`foreign_rate`/
      `foreign_inverse_rate` al Kiosko vía `_load_pos_self_data_fields`, y
      cargar `l10n_ve_pos/static/src/overrides/models/*` en `pos_self_order.assets`
- [x] 5.2 `static/src/app/components/kiosk_amounts_summary/kiosk_amounts_summary.js`
      (nuevo): componente `KioskAmountsSummary` con base imponible, desglose
      de impuestos, total local y total foráneo (reusa
      `get_foreign_total_with_tax()` de `l10n_ve_pos`, sin reimplementar);
      registrado en `CartPage` y `ProductListPage`. Primera versión como
      `patch()` de `PaymentPage`, movido antes de Pagar (ver 7bis.1)
- [x] 5.3 `kiosk_amounts_summary.xml` (nuevo): template del componente +
      `t-inherit` de `CartPage` que reemplaza el Total/Taxes del pie;
      `overrides/product_list_page.xml` lo inserta bajo el resumen de líneas
      del modo solo escaneo
- [x] 5.4 `i18n/es_VE.po`: cadenas nuevas
- [x] 5.5 `tests/test_kiosk_public_routes.py`: `foreign_rate`/
      `foreign_inverse_rate` expuestos en `pos.config` self-data

## 6. Teclado en pantalla (punto 6)

- [x] 6.1 `static/src/app/components/kiosk_keyboard/kiosk_keyboard.js`
      (nuevo): componente OWL, QWERTY + Ñ + numérico, mayúsculas, borrar,
      espacio; `applyShift`/filas del layout exportadas como puras
- [x] 6.2 `static/src/app/components/kiosk_keyboard/kiosk_keyboard.xml`
      (nuevo)
- [x] 6.3 `static/src/app/components/kiosk_keyboard/kiosk_keyboard.scss`
      (nuevo): reusa el estilo de `o_ve_numpad`
- [x] 6.4 `identification_page.js`/`.xml`: mostrar el teclado al enfocar
      nombre/apellido/calle/teléfono; modo numérico para teléfono (cédula
      queda con su numpad propio, sin tocar — ver nota en el reporte)
- [x] 6.5 `i18n/es_VE.po`: cadena nueva ("Space")
- [x] 6.6 `static/tests/unit/kiosk_keyboard.test.js` (nuevo, Hoot): shift y
      layout; `__manifest__.py` registra `web.assets_unit_tests`

## 7. Verificación manual (navegador) — PENDIENTE

- [ ] 7.1 Upgrade del módulo (`-u l10n_ve_pos_self_order`)
- [ ] 7.2 Cancelar una orden → popup en español, "Sí"/"No"
- [ ] 7.3 Crear contacto nuevo → leyenda de obligatorios visible
- [ ] 7.4 Teléfono: operadora inválida / menos de 7 dígitos → rechazado;
      formato válido → se guarda como `0414-1234567`
- [ ] 7.5 Dirección: con el flag activo, crear sin estado/municipio/calle →
      rechazado; con el flag inactivo, se puede omitir
- [ ] 7.6 Carrito (o resumen del modo escaneo): base, impuestos por tasa, total Bs. y total
      foráneo visibles y correctos (coinciden con la factura)
- [ ] 7.7 Teclado en pantalla aparece al enfocar nombre/apellido/teléfono y
      escribe en el campo activo; modo numérico en teléfono
- [ ] 7.8 `binaural_megasoft_self_order` sigue pagando con Megasoft sin
      romperse (compatibilidad del patch de `PaymentPage`)

## 7bis. Observaciones de prueba (23-sep)

- [x] 7bis.1 Con un solo método de pago (lo recomendado: un único Megasoft)
      el core lo auto-selecciona al montar `PaymentPage` y el VPOS abre sin
      dar tiempo a ver el resumen. Se conserva ese salto directo y el resumen
      se mueve ANTES de Pagar: componente `KioskAmountsSummary`
      (`app/components/kiosk_amounts_summary/`, antes
      `overrides/payment_page.{js,xml}`) en el pie del carrito (reemplaza el
      Total/Taxes del core) y bajo el resumen de líneas del modo solo escaneo
- [x] 7bis.2 Teclado numérico: la tecla "C" limpia el campo activo (antes no
      hacía nada) y el teclado se desplaza a la vista al aparecer/cambiar de
      modo (la fila ⌫/0/C quedaba bajo el pliegue en el formulario de cliente
      nuevo)
- [x] 7bis.3 Kiosko en inglés: no era el código — la caja Kiosko no tenía
      idioma por defecto ni idiomas disponibles, y el core pone entonces
      `frontend_lang=en_US`. Se configura en la caja (Autopedido → Idiomas)

## 7ter. Correcciones de QA (24-sep)

- [x] 7ter.1 Teclado: el layout solo cambiaba en `focus`; ahora también en
      `click` del campo, y el teclado hace `mousedown.prevent` para no robar el
      foco del campo activo
- [x] 7ter.2 Teléfono: letras u 8.º dígito seguían visibles (el estado no
      cambiaba → Owl no re-renderizaba el `t-att-value`); el valor saneado se
      reescribe en el input + aviso de 7 dígitos bajo el campo
- [x] 7ter.3 "Crear y continuar" / "Guardar y continuar" ya no se deshabilitan
      por datos incompletos (solo con petición en curso): al pulsarlos se
      muestra qué falta (p. ej. la operadora, cuyo placeholder "Código"
      parecía un valor) — el aviso de error se mueve encima del teclado en
      pantalla (debajo quedaba fuera de la vista)
- [x] 7ter.4 Total foráneo rotulado "Total <moneda>" según `foreign_currency_id`
      (antes "Total (moneda extranjera)")

## 8. OpenSpec

- [x] 8.1 `openspec change validate kiosk-ta-80343-adjustments --strict` →
      válido
