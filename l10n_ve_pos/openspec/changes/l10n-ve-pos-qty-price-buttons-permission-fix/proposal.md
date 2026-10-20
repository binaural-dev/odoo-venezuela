# Fix: los botones Cant./Precio del numpad del PoS nunca se habilitan (l10n_ve_pos)

## Why

Un usuario reportó que en el numpad del PdV (pantalla de venta) no podía
hacer click en los botones **Cant.** y **Precio** — el click no producía
ningún cambio de modo. Al investigar, el botón **%** también estaba
condicionado por Odoo nativo (`manual_discount` / `restrict_price_control` /
rol "mínimo" del empleado, ver `pos_hr`), pero **Cant.** y **Precio** además
dependen de una restricción propia de `l10n_ve_pos`
(`product_screen.js:20-36`) que solo los habilita si el usuario pertenece a
los grupos `l10n_ve_pos.group_change_qty_on_pos_order` /
`group_change_price_on_pos_order`.

El usuario se autoasignó ambos grupos desde Ajustes → Usuarios y el
problema persistió. Causa raíz encontrada:

En Odoo 19, `point_of_sale`'s `res_users.py` (core) solo carga hacia el PdV
`['id', 'name', 'partner_id', 'all_group_ids']`, y en `_load_pos_data_read`
**borra `all_group_ids` después de calcular `_role`**
(`del read_records[0]['all_group_ids']`). El campo `groups_id` que lee
`product_screen.js:15` (`this.pos.user.groups_id`) **nunca existe** en el
objeto que llega al frontend — no es que el usuario no tenga el grupo, es
que el frontend nunca recibe ningún dato de grupos. `userGroups.includes(...)`
sobre `[]` es siempre `false`, para cualquier usuario, en cualquier base de
datos. Esto lleva roto desde la migración a Odoo 19 (en Odoo 17 el
`groups_id` completo sí viajaba al PdV).

## What Changes

- Nuevo `models/res_users.py` en `l10n_ve_pos`: extiende
  `_load_pos_data_read` para inyectar dos booleanos calculados en servidor
  con `has_group()` — `can_change_qty_on_pos_order` y
  `can_change_price_on_pos_order` — siguiendo el mismo patrón que usa el
  core para `_role`.
- `product_screen.js`: reemplaza la lectura de `this.pos.user.groups_id`
  (siempre vacío) por los dos booleanos nuevos.

### Bug 2: los grupos comparten `privilege_id` con el nivel de acceso base del PdV (encontrado al verificar)

El usuario se autoasignó ambos grupos desde Ajustes → Usuarios y el
problema persistió incluso después del fix anterior. Causa: en
`security/res_group.xml`, ambos grupos tenían
`privilege_id="point_of_sale.res_groups_privilege_point_of_sale"` — el
mismo privilegio que usan `group_pos_user` ("Usuario") y `group_pos_manager`
("Administrador"). En Odoo 19, cualquier grupo con `privilege_id` se
renderiza en el formulario de usuario como un **selection field** (dropdown
de una sola opción por privilegio) — ver
`res_user_group_ids_field.js:75-80` en `addons/web`. Solo los grupos SIN
`privilege_id` aparecen como checkboxes independientes bajo "Extra Rights".

Consecuencia real: la fila "Point of Sale" del usuario era un único
dropdown con las opciones Usuario/Administrador/Change quantity/Change
price — nunca dos a la vez. Asignarse "Change quantity on POS order"
probablemente reemplazó su "Administrador"/"Usuario" (perdiendo acceso base
al PdV), y en ningún caso podía tener Cant. Y Precio activos
simultáneamente: el dropdown solo admite un valor.

- `security/res_group.xml`: `privilege_id` de ambos grupos cambiado a
  `eval="False"` (explícito, para que el `-u` lo limpie en upgrade —
  quitar el `<field>` no basta, Odoo no borra valores omitidos). Ahora
  aparecen como checkboxes independientes en "Extra Rights", combinables
  entre sí y con cualquier nivel base de acceso al PdV.

### Bug 3: el `related_models` del cliente descarta las claves nuevas del payload (encontrado al verificar en producción, BD `pos`)

Con los bugs 1 y 2 corregidos y verificados en servidor (`has_group()` en
`odoo shell` devolvía `True`, y un log temporal en `_load_pos_data_read`
confirmó que la llamada RPC real `pos.session/load_data` mandaba
`can_change_qty_on_pos_order=True`), Cant./Precio seguían con el atributo
HTML `disabled` en el DOM real. Se instrumentó `getNumpadButtons()` para
imprimir el valor crudo en el propio texto del botón: mostraba
`undefined`, no `True` — el dato llegaba bien por RPC pero nunca aparecía
en `this.pos.user` del lado cliente.

Causa: el motor `related_models` del PdV (`point_of_sale/static/src/app/
models/related_models/index.js`, método `_sanitizeRawData`) reconstruye
cada record combinando (a) los campos ORM declarados vía
`_load_pos_data_fields()` y (b) claves "extra" que cumplan
`key[0] === "_" && key[1] !== "_"` — el mismo mecanismo que usa el core
para colar `_role` (que NO es un campo ORM real de `res.users`) sin pasar
por `_load_pos_data_fields()`. Cualquier otra clave que no sea un campo
declarado (como nuestro `can_change_qty_on_pos_order`, sin guion bajo)
solo se conserva si `serverData: true` en esa llamada puntual a
`_sanitizeRawData` — condición que no se cumple en el camino que carga
`res.users`, así que la clave se descarta en silencio antes de que
`product_screen.js` la lea. Nunca hubo un error visible: el objeto
simplemente no tenía la propiedad.

- `models/res_users.py`: las dos claves inyectadas pasan a
  `_can_change_qty_on_pos_order` / `_can_change_price_on_pos_order` (con
  guion bajo simple), replicando exactamente la convención de `_role`.
- `product_screen.js`: lee `this.pos.user._can_change_qty_on_pos_order` /
  `_can_change_price_on_pos_order`.

## Impact

- **Capability**: `pos-manual-qty-price-permissions` (nueva).
- **Módulo**: `l10n_ve_pos` (`models/res_users.py`,
  `static/src/overrides/screens/product_screen/product_screen.js`,
  `security/res_group.xml`). `models/__init__.py` actualizado para
  registrar el nuevo modelo.
- **Diagnóstico en vivo (BD `pos`, contenedor `proj`)**: se usó `odoo
  shell` de solo lectura para confirmar `has_group()` y el resultado real
  de `_load_pos_data_read`; se agregó y luego se retiró un
  `_logger.warning` temporal en `res_users.py` para confirmar que la RPC
  real del navegador ejecutaba el código nuevo; se confirmó vía `curl`
  contra el propio contenedor que el JS servido coincidía con el archivo en
  disco. Ninguna de estas dos capas resultó ser la causa — la causa fue el
  bug 3.
- **Riesgo de despliegue**: cambio de comportamiento real — los usuarios que
  YA tienen asignados ambos grupos (o se les asignen a partir de ahora)
  podrán usar Cant./Precio por primera vez desde la migración a V19. Ningún
  usuario podía usarlos antes de este fix, sin importar sus grupos.
- **Acción manual requerida post-deploy**: revisar en Ajustes → Usuarios si
  algún usuario (en particular "Soporte Binaural") quedó sin "Usuario"/
  "Administrador" en Point of Sale por haber seleccionado sin querer uno de
  estos dos grupos en el dropdown exclusivo antes del fix, y restaurarlo.
- Requiere `-u l10n_ve_pos` para registrar el nuevo modelo Python, limpiar
  `privilege_id` en los grupos existentes, y recargar los assets del PdV
  (JS).
