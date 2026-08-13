# Tasks

## 1. Diagnóstico (hecho en esta sesión — solo lectura, sin cambios de código)

- [x] 1.1 Confirmar que el Kiosko no tiene flujo de identificación al inicio:
      el único popup de partner (`PresetInfoPopup`) se dispara desde
      `CartPage.pay()` (antes de pagar), no al empezar, y solo si el preset
      activo tiene `identification='address'`
- [x] 1.2 Confirmar que `validate_partner` (ruta nativa) no pide `vat`/RIF
      en ningún caso (firma del controlador sin ese parámetro)
- [x] 1.3 Localizar el domain de búsqueda por cédula reutilizable:
      `l10n_ve_contact/models/res_partner.py::check_duplicate_vat` (línea 92)
- [x] 1.4 Localizar los defaults de dirección reutilizables:
      `l10n_ve_pos/models/res_partner.py::default_get` +
      `_POS_COMPANY_DEFAULT_FIELDS` (líneas 21-51), gated por el flag de
      contexto `l10n_ve_pos_partner_defaults`
- [x] 1.5 Confirmar que `res.partner.name` es un Char único (sin `lastname`
      propio) y que `prefix_vat`/`vat` son los campos de cédula/RIF
      (`l10n_ve_contact/models/res_partner.py:45-58`)
- [x] 1.6 Localizar el mecanismo de registro de rutas del Kiosko
      (`self_order_index.xml` + `self_order_index.js`, patrón de la ruta
      `"location"` como precedente a mirror) y el punto de entrada
      `LandingPage.start()` (`landing_page.js:97-107`)

## 2. Implementación — Backend

- [ ] 2.1 `l10n_ve_pos_self_order/controllers/__init__.py`,
      `controllers/orders.py`: ruta `/l10n_ve_pos_self_order/kiosk/identify`
      (búsqueda por `prefix_vat`+`vat`, mismo domain que `check_duplicate_vat`)
- [ ] 2.2 Ruta `/l10n_ve_pos_self_order/kiosk/identify/create` (crear
      partner con `default_get(l10n_ve_pos_partner_defaults=True)` para las
      direcciones + `sudo()`, mismo patrón que `validate_partner`)
- [ ] 2.3 Registrar `controllers` en `l10n_ve_pos_self_order/__init__.py`

## 3. Implementación — Frontend

- [ ] 3.1 `static/src/app/pages/identification_page/identification_page.js`
      + `.xml`: Paso A (prefix_vat + cédula) → Paso B (nombre, apellido,
      teléfono) condicional a "no encontrado"
- [ ] 3.2 `static/src/overrides/landing_page.js`: patch `start()`,
      gateado ESTRICTAMENTE por `self_ordering_mode === 'kiosk'` (no debe
      afectar el flujo `mobile`/QR de mesas)
- [ ] 3.3 `static/src/overrides/self_order_index.js` + template XML:
      `t-inherit` del slot `"identification"` + registro del componente
      en `selfOrderIndex.components`
- [ ] 3.4 `__manifest__.py`: añadir bloque `"assets": {"pos_self_order.assets": [...]}`
      (el módulo hoy no declara assets)
- [ ] 3.5 Verificar en implementación si `selfOrder.currentOrder` existe
      como objeto local antes de `product_list`, o si `IdentificationPage`
      necesita forzar su creación antes de asignar `partner_id`

## 4. Tests

- [ ] 4.1 Test Python: cédula existente → la ruta de búsqueda devuelve el
      partner correcto (id/name/phone), sin datos privados extra
- [ ] 4.2 Test Python: cédula no existente → la ruta de creación arma el
      partner con `name` = nombre+apellido concatenado, `phone`,
      `prefix_vat`/`vat`, y las direcciones precargadas desde
      `env.company.partner_id` (mismo criterio que
      `l10n-ve-pos-partner-quick-form-company-defaults`)
- [ ] 4.3 Test Python: creación respeta el mismo comportamiento del
      `default_get` original (no pisa valores ya resueltos, se abstiene si
      hay `parent_id`) — reutilizar los casos de aquel change si aplican
- [ ] 4.4 Correr la suite en el contenedor `proj` — pendiente, no
      ejecutado en este pase (el usuario la corre)

## 5. Verificación manual (navegador, por el usuario)

- [ ] 5.1 Kiosko: "Empezar pedido" → pide cédula antes de mostrar catálogo
- [ ] 5.2 Cédula existente → pasa directo a productos con `partner_id` fijado
- [ ] 5.3 Cédula nueva → pide nombre/apellido/teléfono, crea el contacto,
      confirmar en backoffice que la dirección quedó igual a la de la
      compañía
- [ ] 5.4 Orden retomada (recarga de página con orden en curso) no vuelve a
      pedir cédula si ya tiene `partner_id`
- [ ] 5.5 Regresión: modo `mobile`/QR de mesas sigue funcionando igual
      (el patch de `LandingPage.start()` no debe afectarlo)
- [ ] 5.6 Factura generada desde un pedido del Kiosko sale con el cliente
      identificado, no con el consumidor genérico

## 6. OpenSpec

- [x] 6.1 `openspec change validate l10n-ve-pos-self-order-kiosk-partner-identification` → válido
