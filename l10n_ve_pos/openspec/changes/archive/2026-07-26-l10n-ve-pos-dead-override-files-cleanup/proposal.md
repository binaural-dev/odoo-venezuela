# Limpieza: ficheros de override del PdV 100% comentados o vacíos (l10n_ve_pos)

## Why

Durante la migración V17 → V19, varias personalizaciones del frontend del
PdV se desactivaron comentando el fichero entero en lugar de borrarlo. El
manifest los sigue empaquetando, porque los assets se declaran con globs
(`__manifest__.py:38-41`): `"l10n_ve_pos/static/src/**/**"` mete en el
bundle del PdV cualquier fichero bajo `static/src`, incluido uno cuyo
contenido es íntegramente comentario.

El coste no es de ejecución — un fichero comentado no hace nada — sino de
**lectura**: en cada migración y en cada depuración esos ficheros
aparecen en las búsquedas como si fueran código vigente y hay que
descartarlos a mano. La exploración previa al change
`l10n-ve-pos-partner-quick-form-company-defaults` tropezó exactamente con
esto: `partner_list.js` (con su `createPartner()` comentado) parecía la
mitad viva del flujo de creación de contactos del PdV.

El caso más engañoso es `product_list.js`: la característica que
implementaba —filtrar productos sin stock según
`pos_show_just_products_with_available_qty`— **sí está viva**, pero
reimplementada en
`static/src/overrides/screens/product_screen/product_screen.js:77` y en
`models/product_product.py:66`. Quien encontrase primero el fichero
comentado podía concluir que la característica estaba desactivada.

## What Changes

Se eliminan los 7 ficheros muertos que quedaban bajo `static/src`:

| Fichero | Estado | Qué hacía |
| --- | --- | --- |
| `overrides/models/pos_model.js` | 257 líneas, 100% comentado | `_processData` cargaba las claves ad-hoc `pos.cities` y `pos.prefix_vats`, prohibidas en Odoo 19 (`models/pos_session.py:19-26`) |
| `overrides/models/product_model.js` | 19 líneas, 100% comentado | `patch(Product.prototype)` con `get_foreign_price` sobre la API V17 (`@point_of_sale/app/store/models`, inexistente en V19) |
| `overrides/screens/partner_list/partner_list.js` | 35 líneas, 100% comentado | `updatePartnerList` + `createPartner()` que preseteaba país/estado y el `vat` desde la búsqueda |
| `overrides/screens/partner_list/partner_list.xml` | 8 líneas, solo el wrapper `<templates>` | añadía una columna "Document" a `point_of_sale.PartnerList` |
| `overrides/screens/product_screen/actionpad_widget.xml` | 9 líneas, solo el wrapper `<templates>` | mostraba `(prefix_vat + vat)` junto al nombre del cliente |
| `overrides/screens/product_screen/product_list.js` | 25 líneas, 100% comentado | filtro de productos sin stock, **hoy reimplementado** en `product_screen.js:77` |
| `overrides/screens/payment_screen/payment_screen_top.js` | 0 bytes | fichero vacío; el override vivo es `payment_screen_top.xml` (`t-name="PaymentScreenDue"`) |

Verificado antes de borrar:

- Los 4 ficheros `.js` no tienen ni una línea activa; los 2 `.xml` solo
  conservan el wrapper `<templates>` vacío, así que no definían ninguna
  plantilla OWL.
- Ningún fichero de `l10n_ve_pos`, `l10n_ve_pos_mf`, `l10n_ve_pos_igtf`
  ni `integra-addons` los importa ni hereda sus plantillas: los únicos
  `import` que los mencionan están dentro de los propios ficheros
  comentados.
- Los flags de configuración que consumían siguen vivos con otro
  consumidor: `pos_show_just_products_with_available_qty`
  (`product_screen.js:77`, `product_product.py:66`) y `pos_show_free_qty`
  (`product_card.js:49`).

No hay cambio de comportamiento: se elimina código que ya no se
ejecutaba. La historia de cada personalización queda en git (ver
`git log --diff-filter=D` y la rama `19.0`).

Además, y como parte de este change, se documenta en
`removed-features.md` **qué característica tenía cada fichero y en qué
estado está hoy** (MIGRADA / SUPERADA / NO MIGRADA), con el comando
`git show` para recuperarlo. En esta migración ha ocurrido varias veces
que algo comentado terminó haciendo falta, así que borrar el fichero no
debe borrar la memoria de la característica.

Ese inventario destapó dos cosas que no son solo documentación:

- **La validación de existencias al enviar la orden no está operativa en
  V19.** `pos_model.js` tenía `update_products()` +
  `push_orders`/`push_single_order`, que refrescaban el stock antes de
  enviar la orden con la API V17
  `pos.session.get_pos_ui_product_product_by_params`. Consecuencia: los
  controladores `/validate_products_order` (`controllers/controller.py:13`)
  y `/validate_products_in_warehouse` (`controllers/controller.py:39`)
  siguen definidos en Python **sin ningún llamador en todo `src/`**.
- **El `compute_all` custom (~200 líneas) era una copia del motor de
  impuestos nativo de V17 con un delta no documentado** (sin ninguna
  referencia a moneda foránea, IGTF ni tasa en su cuerpo). Queda anotado
  cómo aislarlo si algún día aparece un descuadre de impuestos.

## Impact

- **Capability**: `pos-odoo19-frontend` (añade requirement).
- **Módulo**: `l10n_ve_pos`, solo assets del frontend. Requiere
  `-u l10n_ve_pos` para reconstruir el bundle del PdV (los bundles se
  cachean; ver `openspec/migration-lessons.md`).
- **Riesgo de despliegue**: bajo. Ninguno de los ficheros aportaba
  comportamiento; el único riesgo teórico sería un `import` colgante, y
  se comprobó que no existe en ningún módulo del despliegue.
- **Fuera de alcance (pendiente, no corregido en este change)**:
  - `pos.config.validate_phone_in_pos` (`models/pos_config.py:37`) sigue
    siendo un campo huérfano: sin consumidor ni vista desde que se borró
    el editor de contactos V17.
  - `res.company.pos_show_free_qty_on_warehouse` (`models/res_company.py:12`)
    tiene campo, related en `pos.config` y bloque en los ajustes
    (`views/res_config_settings.xml:146-154`), pero **ningún lector** en
    Python ni en JS — flag huérfano a decidir si se implementa o se
    elimina.
  - Los globs del manifest siguen siendo redundantes
    (`static/src/**/**`, `static/src/**/**/**/*` y la ruta explícita de
    `payment_model.js` describen el mismo conjunto); simplificarlos es
    una limpieza aparte.
