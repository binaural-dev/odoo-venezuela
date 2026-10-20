# Tasks

## 1. Diagnóstico y diseño

- [x] 1.1 Confirmar que `PartnerDetailsEdit` no existe en Odoo 19 y que
      el PdV crea/edita `res.partner` vía
      `point_of_sale.res_partner_action_edit_pos` +
      `PosStore.editPartner()` (`pos_store.js:2307-2318`), abriendo la
      vista form real del backoffice (`base.view_partner_form`)
- [x] 1.2 Localizar en git los commits que eliminaron el editor V17
      (`cc8e92216` — XML, `a4131fe8b` — JS) y confirmar que
      `pos.prefix_vats` / `pos.cities` ya no son viables en Odoo 19
      (`models/pos_session.py:19-26`, claves top-level no-modelo rompen
      `RecordStore` en el bootstrap)
- [x] 1.3 Verificar contra el arch real de `base.view_partner_form` y el
      core de `point_of_sale`/`base` en Odoo 19 (`ir_ui_view.py`
      `_get_combined_archs`, `ir_actions.py:308` `view_id
      ondelete='set null'`, `res_company.py:54-63`, `res_partner.py:
      584-587`) qué xpaths y qué mecanismo de `default_get` son
      correctos
- [x] 1.4 Decidir vista `mode="primary"` (no extensión con
      `groups`/`invisible`), `context` de la acción (no
      `PosStore.editPartnerContext()`), `default_get` server-side (no
      `default_*` en el `context` de la acción) y `replace` vacío (no
      `invisible`) para los recortes — ver `design.md`

## 2. Implementación

- [x] 2.1 `views/res_partner_views.xml`: nueva vista
      `l10n_ve_pos.view_partner_form_pos`, `inherit_id =
      base.view_partner_form`, `mode="primary"`, `priority=100`, con los
      recortes (`button_box`, `image_1920`, `website`, `lang`,
      `category_id`, `properties`, `notebook` completo) y el reemplazo
      de `function` por `barcode`
- [x] 2.2 Sobreescribir `point_of_sale.res_partner_action_edit_pos`:
      `view_id` a la vista reducida, `context =
      {'l10n_ve_pos_partner_defaults': True}`
- [x] 2.3 `models/res_partner.py`: `default_get` que precarga
      `country_id`, `state_id`, `city_id`, `municipality`, `parish_id`,
      `zip` desde `env.company.partner_id` bajo el flag de contexto,
      respetando valores ya resueltos por `super()` y absteniéndose con
      `parent_id`/`default_parent_id`
- [x] 2.4 `__manifest__.py`: registrar `views/res_partner_views.xml` en
      `data`
- [x] 2.5 Verificar sintaxis (XML bien formado, xpaths cotejados contra
      el arch real; `ast.parse` del Python) — sin acceso a Odoo cargado
      para correr el módulo completo en este pase

## 3. Validación

- [x] 3.1 `-u l10n_ve_pos` en el contenedor `proj` — ejecutado por el
      usuario (2026-07-26)
- [x] 3.2 Verificación en navegador (usuario): crear un cliente nuevo
      desde el PdV y confirmar que los campos de localización
      (país, estado, ciudad, municipio, parroquia, C.P.) ya vienen
      precargados con la dirección de la compañía
- [x] 3.3 Verificación en navegador (usuario): editar un cliente
      existente desde el PdV y confirmar que se ve el formulario
      reducido con sus valores actuales, sin defaults de compañía
      pisando nada
- [x] 3.4 Verificación en navegador (usuario): abrir el mismo contacto
      desde Contactos en el backoffice y confirmar que el formulario
      completo sigue idéntico (pestañas, foto, etiquetas, propiedades)

Verificado en navegador por el usuario el 2026-07-26: comportamiento
correcto en los tres flujos (crear desde el PdV, editar desde el PdV,
formulario de backoffice intacto).

## 4. OpenSpec

- [x] 4.1 `openspec validate l10n-ve-pos-partner-quick-form-company-defaults --type change --strict --no-interactive` →
      `Change 'l10n-ve-pos-partner-quick-form-company-defaults' is valid`

## 5. Pendiente (fuera de alcance de este change, con seguimiento)

- [ ] 5.1 Cobertura de tests del `default_get` y de la vista reducida
      (no se escribieron en este pase, por indicación explícita del
      usuario)
- [ ] 5.2 Reimplantar las validaciones que tenía el editor V17 (RIF
      obligatorio, teléfono `/^0[24]\d{9}$/`, calle y país obligatorios)
      si se consideran necesarias — hoy las cubren en parte los
      `required` de vista de `l10n_ve_contact` y `l10n_ve_location`.
      `pos.config.validate_phone_in_pos` (`models/pos_config.py:37`)
      sigue siendo un campo huérfano sin consumidor ni vista
- [ ] 5.3 Limpiar los ficheros muertos 100% comentados que el manifest
      sigue empaquetando por los globs de `static/src/**`:
      `screens/partner_list/partner_list.{js,xml}`,
      `screens/product_screen/actionpad_widget.xml`,
      `overrides/models/pos_model.js`
- [ ] 5.4 Revisar el caso preexistente de `l10n_ve_igtf`: si está
      instalado y la compañía no tiene configuradas sus cuentas de
      anticipo, crear contactos falla por `required=True` sin default
      efectivo — condición ya presente también en backoffice, no
      introducida por este change
