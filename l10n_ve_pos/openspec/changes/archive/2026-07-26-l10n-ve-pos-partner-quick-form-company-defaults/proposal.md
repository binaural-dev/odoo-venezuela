# Feature: formulario reducido de contacto en el PdV con datos de la compañía por defecto (l10n_ve_pos)

## Why

En V17, `l10n_ve_pos` reescribía a mano el editor de clientes del PdV con
`static/src/overrides/screens/partner_editor/{partner_editor.js,partner_editor.xml}`
(inyectaba `prefix_vat`, `vat`, un `<select>` de `city_id` alimentado por
las claves ad-hoc `pos.prefix_vats` / `pos.cities`, y validaciones de
cédula, teléfono `/^0[24]\d{9}$/`, calle y país). Esa personalización se
eliminó en la migración: el XML en el commit `cc8e92216` ("[MIG]
l10n_ve_pos: corrige tasa BCV y limpia herencias") y el JS en `a4131fe8b`
("[IMP] l10n_ve_pos: migra loaders PoS a Odoo 19").

Motivo: **en Odoo 19 el componente `PartnerDetailsEdit` ya no existe**. El
PdV abre la acción `point_of_sale.res_partner_action_edit_pos`
(`target="new"`, `view_id = base.view_partner_form`) mediante
`PosStore.editPartner()`
(`addons/point_of_sale/static/src/app/services/pos_store.js:2307-2318`)
envuelta en `makeActionAwaitable`, y renderiza la **vista form real del
backoffice** dentro de un diálogo — el formulario del PdV es hoy un
espejo literal del de Contactos.

Consecuencias que motivan el change:

1. El cajero ve el formulario completo: pestañas (Contactos y
   direcciones, Ventas y Compras, Notas), foto, propiedades, idioma,
   sitio web, etiquetas y los campos que otros módulos VE inyectan; y
   debe teclear a mano estado, ciudad, municipio, parroquia y C.P., que
   `l10n_ve_location` marca `required="1"`
   (`l10n_ve_location/views/res_partner_views.xml:21,30,36`). Es lento en
   caja, que es un puesto de trabajo cronometrado.
2. Cualquier ajuste por herencia de extensión sobre
   `base.view_partner_form` afectaría también al backoffice, que es un
   requisito explícito a NO romper.

## What Changes

- Nueva vista `l10n_ve_pos.view_partner_form_pos`
  (`views/res_partner_views.xml`), heredada `mode="primary"` de
  `base.view_partner_form`, con `priority=100`. Con `mode="primary"` Odoo
  compone el arch del padre ya con todas sus vistas de extensión
  aplicadas y aplica el diff propio sobre esa copia, sin tocar el arch de
  `base.view_partner_form` — se heredan gratis `prefix_vat`/`vat`
  (`l10n_ve_contact`) y el bloque de dirección venezolano de
  `l10n_ve_location`.
- Recortes del formulario del PdV, todos con `position="replace"` vacío
  (se elimina el nodo, no se oculta, para no dejar `required` de vista
  colgando): `button_box`, `image_1920`, `website`, `lang`,
  `category_id`, `properties` y el `notebook` completo.
  `field[@name='function']` se sustituye por `<field name="barcode"/>`
  para preservar el `barcode` que `point_of_sale` coloca dentro del
  notebook eliminado.
- Se sobreescribe la acción nativa
  `point_of_sale.res_partner_action_edit_pos` para apuntar `view_id` a la
  vista reducida y añadir `context = {'l10n_ve_pos_partner_defaults':
  True}`. Esa acción la usa exclusivamente el PdV (`pos_store.js:2310`) y
  ningún módulo de `src/` la sobreescribía.
- Nuevo `default_get` en `models/res_partner.py` que, solo bajo el flag
  de contexto `l10n_ve_pos_partner_defaults`, rellena `country_id`,
  `state_id`, `city_id`, `municipality`, `parish_id` y `zip` desde
  `env.company.partner_id`. Nunca sobreescribe un valor ya resuelto por
  `super()` y se abstiene por completo si hay `parent_id` /
  `default_parent_id`.
- `city` (Char) queda deliberadamente fuera de los defaults: es
  `related="city_id.name"` con `store=True` y escribible, así que
  escribirla renombraría el registro `res.country.city`; se rellena sola
  al fijar `city_id`.

## Capabilities

### New Capabilities

- `pos-partner-quick-form`: formulario form reducido de `res.partner`
  para el PdV, derivado sin tocar el backoffice, con precarga de
  localización desde la dirección de la compañía.

## Impact

- **Capability**: `pos-partner-quick-form` (nueva).
- **Módulo**: `l10n_ve_pos` — `views/res_partner_views.xml` (nuevo),
  `__manifest__.py`, `models/res_partner.py`. Requiere `-u l10n_ve_pos`
  para cargar la vista nueva y el override de la acción.
- **No afecta al backoffice**: `base.view_partner_form` no se modifica;
  el `default_get` solo actúa bajo el flag de contexto que únicamente
  inyecta la acción del PdV. Verificado además que ningún campo
  obligatorio a nivel de modelo queda fuera del formulario reducido:
  `default_document` (`l10n_ve_stock_account`) tiene `default="invoice"`
  y `default_advance_{customer,supplier}_account_id` (`l10n_ve_igtf`)
  toman su default de la compañía.
- **Riesgo de despliegue**: bajo. Todo el cambio es declarativo (una
  vista nueva + dos campos de una acción) más un `default_get` guardado
  por flag de contexto. Si la vista fallara, el remedio es apuntar
  `view_id` de nuevo a `base.view_partner_form`.
- **Verificación**: estática (XML bien formado, xpaths cotejados contra
  el arch real de `base.view_partner_form`, `ast.parse` del Python) +
  prueba en navegador por parte del usuario. Sin tests automatizados en
  este pase, por indicación explícita del usuario.
- **Fuera de alcance (pendiente, no corregido en este change)**:
  - Cobertura de tests del `default_get` y de la vista reducida (no se
    escribieron en este pase por indicación del usuario).
  - Las validaciones que tenía el editor V17 (RIF obligatorio, teléfono
    `/^0[24]\d{9}$/`, calle y país obligatorios) no se reimplantan; hoy
    las cubren en parte los `required` de vista de `l10n_ve_contact` y
    `l10n_ve_location`. `pos.config.validate_phone_in_pos`
    (`models/pos_config.py:37`) sigue siendo un campo huérfano sin
    consumidor ni vista.
  - Ficheros muertos 100% comentados que el manifest sigue empaquetando
    por los globs de `static/src/**`:
    `screens/partner_list/partner_list.{js,xml}`,
    `screens/product_screen/actionpad_widget.xml`,
    `overrides/models/pos_model.js`.
  - Si `l10n_ve_igtf` está instalado y la compañía no tiene configuradas
    sus cuentas de anticipo, crear contactos falla por `required=True`
    sin default efectivo — condición preexistente, también en
    backoffice.
