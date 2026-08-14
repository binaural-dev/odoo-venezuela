# Spec delta: pos-manual-qty-price-permissions

## ADDED Requirements

### Requirement: Los booleanos de permiso viajan al PdV calculados en servidor

El sistema SHALL calcular `_can_change_qty_on_pos_order` y
`_can_change_price_on_pos_order` en `res.users._load_pos_data_read` usando
`has_group()` sobre `l10n_ve_pos.group_change_qty_on_pos_order` /
`l10n_ve_pos.group_change_price_on_pos_order`, e incluirlos en el registro
de usuario que se envía al PdV. El sistema SHALL NOT depender de un campo
`groups_id` sin procesar en el cliente (Odoo 19 no lo envía).

#### Scenario: Usuario con ambos grupos asignados

- **GIVEN** un usuario asignado a `group_change_qty_on_pos_order` y
  `group_change_price_on_pos_order`
- **WHEN** se carga el PdV
- **THEN** `this.pos.user._can_change_qty_on_pos_order` y
  `_can_change_price_on_pos_order` son `true`

#### Scenario: Usuario sin los grupos

- **GIVEN** un usuario sin ninguno de los dos grupos
- **WHEN** se carga el PdV
- **THEN** ambos booleanos son `false`

### Requirement: Los botones Cant./Precio del numpad respetan esos booleanos

El sistema SHALL deshabilitar el botón **Cant.** del numpad cuando
`_can_change_qty_on_pos_order` es `false`, y el botón **Precio** cuando
`_can_change_price_on_pos_order` es `false`, sobre el resultado de
`getNumpadButtons()` nativo (que ya deshabilita Precio/% por reglas propias
de Odoo — `manual_discount`, `restrict_price_control`, rol "mínimo" del
cajero).

#### Scenario: Click en Cant./Precio habilitados

- **GIVEN** un usuario con ambos grupos y sin restricciones nativas activas
- **WHEN** hace click en Cant. o Precio en el numpad
- **THEN** el modo del numpad cambia (el botón no tiene el atributo
  `disabled`)

### Requirement: Las claves extra inyectadas en `_load_pos_data_read` usan guion bajo simple

El sistema SHALL prefijar con un único guion bajo (`_nombre`, nunca
`__nombre` ni `nombre` a secas) cualquier clave inyectada en un `dict` de
`_load_pos_data_read` que no sea un campo ORM real declarado en
`_load_pos_data_fields`. El
`related_models` del cliente PdV (`_sanitizeRawData` en
`related_models/index.js`) solo conserva sin condición las claves que
cumplen `key[0] === "_" && key[1] !== "_"`; cualquier otra clave no
declarada SHALL NOT asumirse presente en el registro del lado cliente.

#### Scenario: Clave sin guion bajo se pierde en el cliente

- **GIVEN** `_load_pos_data_read` de `res.users` agrega la clave
  `can_change_qty_on_pos_order` (sin guion bajo) al dict devuelto
- **WHEN** el PdV carga los datos vía `pos.session/load_data`
- **THEN** `this.pos.user.can_change_qty_on_pos_order` es `undefined` en el
  cliente, aunque el payload RPC sí la incluya

#### Scenario: Clave con guion bajo simple sobrevive

- **GIVEN** `_load_pos_data_read` agrega `_can_change_qty_on_pos_order`
- **WHEN** el PdV carga los datos
- **THEN** `this.pos.user._can_change_qty_on_pos_order` refleja el valor
  calculado en servidor

### Requirement: Los grupos venezolanos son independientes del nivel de acceso base al PdV

`group_change_qty_on_pos_order` y `group_change_price_on_pos_order` SHALL NOT
tener `privilege_id`. El sistema SHALL permitir que un usuario tenga
cualquier combinación de estos dos grupos junto con `group_pos_user` o
`group_pos_manager` simultáneamente.

#### Scenario: Asignar ambos permisos sin perder el nivel de acceso base

- **GIVEN** un usuario con `group_pos_user` (o `group_pos_manager`)
- **WHEN** un administrador le marca los checkboxes "Change quantity on POS
  order" y "Change price on POS order" en Ajustes → Usuarios
- **THEN** el usuario conserva su nivel de acceso al PdV (Usuario/
  Administrador) Y ambos permisos quedan activos a la vez
