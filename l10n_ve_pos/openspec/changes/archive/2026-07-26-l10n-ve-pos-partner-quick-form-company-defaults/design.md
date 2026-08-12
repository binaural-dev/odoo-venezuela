# Design: formulario reducido de contacto en el PdV (l10n_ve_pos)

## Contexto

Odoo 19 eliminó el componente OWL a medida que el PdV V17 usaba para
editar clientes (`PartnerDetailsEdit`). Hoy `PosStore.editPartner()`
(`addons/point_of_sale/static/src/app/services/pos_store.js:2307-2318`)
abre la acción `point_of_sale.res_partner_action_edit_pos`
(`target="new"`) envuelta en `makeActionAwaitable`, y esa acción apunta
`view_id` a `base.view_partner_form` — la vista form completa del
backoffice. El mismo patrón lo usa el PdV para productos
(`product_template_action_edit_pos`, línea 2326 del mismo archivo): abrir
la vista real del backoffice dentro de un diálogo, no reimplementar un
editor propio.

La restricción dura es que **nada de esto puede tocar
`base.view_partner_form`**: cualquier herencia sobre esa vista se ve
también en Contactos del backoffice, y ese formulario debe seguir siendo
el completo.

## Decisiones

### a) Vista derivada `mode="primary"`, no una extensión con `groups`/`invisible`

Se consideró heredar `base.view_partner_form` en modo extensión (el modo
por defecto) y ocultar nodos con `invisible` condicionado a un grupo de
seguridad o a una marca de contexto. Se descartó porque:

- Una herencia en modo extensión modifica el arch base compartido —
  exactamente lo que no se puede hacer. `invisible` no evita esto: sigue
  siendo la misma vista `ir.ui.view` que resuelve el backoffice, solo con
  nodos escondidos por JS, y el campo `required` de vista (p. ej.
  `city_id`, `municipality`, `parish_id` en
  `l10n_ve_location/views/res_partner_views.xml:21,30,36`) seguiría
  bloqueando el guardado aunque el nodo esté oculto.
- `mode="primary"` con `priority=100` crea una vista **nueva e
  independiente**: Odoo compone el arch del padre ya con todas sus
  extensiones aplicadas (`_get_combined_archs`,
  `odoo/addons/base/models/ir_ui_view.py`) y aplica el diff propio sobre
  esa copia. El arch de `base.view_partner_form` en sí queda intacto —
  cero riesgo de fuga hacia el backoffice. `priority=100` (frente al
  `priority=1` del padre) evita que esta vista gane ninguna resolución
  por defecto si en algún momento se busca la vista primary de
  `res.partner` sin `view_id` explícito.

### b) `context` de la acción, no `PosStore.editPartnerContext()`

`pos_store.js` expone un punto de extensión pensado exactamente para
esto: `editPartnerContext(partner)` (línea 2301), que por defecto
devuelve `{}` y se pasa como `additionalContext` a `makeActionAwaitable`
(línea 2313). Parchearlo con un `patch()` de `PosStore` para devolver
`{ l10n_ve_pos_partner_defaults: true }` habría evitado tocar la acción
nativa. Se descartó por dos motivos:

1. `editPartner()` invoca `this.editPartnerContext()` **sin pasarle el
   argumento `partner`** (línea 2313: `this.editPartnerContext()`, no
   `this.editPartnerContext(partner)`) — el hook recibe siempre
   `undefined`, así que no sirve para distinguir "editar existente" de
   "crear nuevo" sin leer otro estado del store.
2. Es un patch de JS del lado del store del PdV, cuando el efecto
   deseado (defaults de localización) es una operación 100% de backend
   sobre `res.partner`. Forzar ese contexto desde el cliente solo para
   que el servidor lo lea en `default_get` es indirección innecesaria:
   la acción de servidor ya tiene un campo `context` declarativo
   pensado para esto.

Sobreescribir los dos campos (`view_id`, `context`) de la acción
`point_of_sale.res_partner_action_edit_pos` es más simple, no requiere
tocar JS, y es coherente con que `view_id` es `ondelete='set null'`
(`odoo/addons/base/models/ir_actions.py:308`): si `l10n_ve_pos` se
desinstala, la acción queda funcionando con la vista y el contexto por
defecto de Odoo, sin registro roto.

### c) `default_get` server-side, no claves `default_*` en el `context` de la acción

Se consideró resolver los valores directamente en el `context` de la
acción con claves `default_country_id`, `default_state_id`, etc. Se
descartó porque esas claves son estáticas en el XML de la acción — no
pueden leer `env.company.partner_id` en tiempo de ejecución (multi-
compañía, o una compañía cuya dirección cambie). Además, los `default_*`
del contexto se filtran también hacia los quick-create de relaciones
x2many que puedan aparecer en la vista, lo cual es un efecto colateral no
deseado. Un `default_get` override en el modelo:

- Corre en el momento correcto (creación de un `res.partner` nuevo desde
  el diálogo del PdV).
- Puede leer `env.company.partner_id` (el partner de la compañía activa)
  en vivo.
- Respeta cualquier `default_*` que sí venga del contexto o cualquier
  default de campo ya resuelto por `super()` — nunca pisa un valor que
  Odoo ya decidió, incluido el país que ya fija `l10n_ve_contact` por
  defecto.

`res.company` no tiene los campos de localización venezolanos
directamente: `street`/`street2`/`zip`/`city`/`state_id`/`country_id` son
compute/inverse sobre `partner_id`
(`odoo/addons/base/models/res_company.py:54-63`), y `city_id` /
`municipality` / `parish_id` los añade `l10n_ve_location` sobre
`res.partner` (`l10n_ve_location/models/res_partner.py:7-15`) — no
existen en `res.company` en absoluto. Por eso el `default_get` lee de
`env.company.partner_id`, no de `env.company` directamente.

Se abstiene por completo si el contacto tiene `parent_id` (edición) o
`default_parent_id` (creación de un hijo desde un o2m, p. ej. una
dirección de entrega) — un contacto hijo hereda la dirección de su
padre, no la de la compañía; escribirle los defaults de compañía ahí
sería incorrecto.

`country_id` se incluye en los defaults (aunque `l10n_ve_contact` ya fija
un default propio a `base.ve`) por coherencia con `state_id`: si algún
día la compañía tuviera un país distinto, fijar ambos a la vez evita que
`_onchange_country_id`
(`odoo/addons/base/models/res_partner.py:584-587`) borre `state_id` por
detectar que no coincide con el país — el `default_get` no dispara
onchanges, pero mantiene el par consistente para cuando el formulario sí
los evalúe.

### d) Eliminar nodos (`position="replace"` vacío), no ocultarlos

Se consideró `invisible="1"` sobre los mismos nodos en vez de
`replace`. Se descartó porque varios de los campos escondidos por
defecto (`city_id`, `municipality`, `parish_id`, dentro del notebook
eliminado si se hubiera optado por ocultarlo entero) llevan `required` a
nivel de vista en la herencia de `l10n_ve_location`. Un campo
`invisible` pero `required` sigue bloqueando el guardado del formulario
con un error de validación que el cajero no puede resolver porque no ve
el campo. `replace` vacío elimina el nodo del arch compuesto por
completo — no hay `required` fantasma.

### e) No se reimplanta el editor OWL a mano

La deuda técnica real de la V17 era mantener un editor de contacto
paralelo (`partner_editor.js`/`.xml`) sincronizado a mano con cualquier
cambio del núcleo de Odoo en `res.partner`, y ese editor dependía de
claves top-level ad-hoc en el payload de bootstrap del PdV
(`pos.prefix_vats`, `pos.cities`) para poblar sus selects. Esas claves ya
no son viables en Odoo 19: `models/pos_session.py:19-26` documenta
explícitamente que el payload de `load_data` solo admite claves-modelo —
agregar una clave top-level no-modelo rompe el parseo de `RecordStore` en
el bootstrap del PdV ("Index 'id' not defined for model ..."), que fue
justamente el bug que forzó a limpiar el editor legado en la migración.

Reutilizar la vista form real del backoffice (como ya hace el núcleo de
Odoo 19 para clientes y productos) evita reconstruir ese editor: no hay
selects a poblar vía claves ad-hoc, no hay lógica de validación
duplicada, y cualquier campo nuevo que otro módulo VE agregue al form de
`res.partner` (p. ej. `taxpayer_type` de `l10n_ve_tax_payer`) aparece
automáticamente en el PdV sin tocar este módulo.

## Riesgos / Trade-offs

- [Riesgo] Un módulo futuro que agregue un campo `required` al form de
  `res.partner` fuera del notebook y fuera de los nodos recortados
  aparecerá también en el formulario reducido del PdV, sin control desde
  `l10n_ve_pos`. → Mitigación: es el comportamiento deseado (el
  formulario reducido hereda del backoffice, no lo reemplaza); si algún
  campo nuevo resultara inadecuado para caja, se recorta con un xpath
  adicional en `view_partner_form_pos`.
- [Riesgo] Si `base.view_partner_form` cambia su estructura en una
  futura versión de Odoo, los xpaths de los recortes podrían dejar de
  resolver. → Mitigación: los xpaths se cotejaron contra el arch real
  vigente; es el mismo riesgo que ya asume cualquier herencia de
  `l10n_ve_contact`/`l10n_ve_location` sobre la misma vista base.
- [Riesgo] Sin tests automatizados en este pase (decisión explícita del
  usuario) — una regresión futura en `default_get` no se detectaría por
  CI. → Mitigación: queda registrado como pendiente de seguimiento en
  `tasks.md`.

## Plan de migración

Ninguno — es una vista y un `default_get` nuevos, sin cambios de schema
ni de datos existentes. Desplegar requiere `-u l10n_ve_pos`. Rollback:
revertir el commit; si solo se quisiera desactivar sin revertir, apuntar
`view_id` de `res_partner_action_edit_pos` de vuelta a
`base.view_partner_form` es suficiente y no requiere tocar
`default_get` (el flag de contexto simplemente deja de inyectarse).

## Preguntas abiertas

Ninguna pendiente de decisión — el diseño fue verificado y confirmado
antes de este change.
