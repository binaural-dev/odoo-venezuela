# Fix: `group_authorized_discount_pos` comparte `privilege_id` con el acceso base al PdV

## Why

El usuario reportó que el "descuento autorizado" seguía sin funcionar tras
un pedido previo de cambiar el `privilege_id` para que se comportara como
`group_change_qty_on_pos_order`/`group_change_price_on_pos_order` (fix
`6ed3af6a9`, ver `l10n-ve-pos-qty-price-buttons-permission-fix`).

Al revisar, `l10n_ve_pos.group_authorized_discount_pos`
(`data/res_group.xml`) nunca recibió ese fix: seguía con
`privilege_id="point_of_sale.res_groups_privilege_point_of_sale"`, el mismo
privilegio que `group_pos_user`/`group_pos_manager`. En Odoo 19 esto lo
renderiza como un select de una sola opción en el form de usuario (ver
`res_user_group_ids_field.js`), haciéndolo mutuamente excluyente con el
nivel de acceso base al PdV — el mismo Bug 2 documentado en el fix de
Cant./Precio.

Investigación adicional (búsqueda en todo `src/`, historial completo desde
el commit original `d5c94d1da` de mayo 2025): `group_authorized_discount_pos`
nunca ha sido leído por ningún código — ni `has_group()` en Python, ni
`product_screen.js`, ni ningún otro módulo. La autorización real de
descuentos en el PdV hoy la resuelve otro mecanismo
(`binaural_pos_hr.pos_discount_require_supervisor_key` +
`SupervisorPopup`, PIN/barcode contra `pos.supervisor_ids`), no este grupo.
Por decisión explícita del usuario, este change se limita a corregir el
`privilege_id` (paridad con Cant./Precio en Ajustes → Usuarios); NO añade
ninguna verificación nueva de este grupo en el numpad de descuento.

## What Changes

- `data/res_group.xml`: `privilege_id` de `group_authorized_discount_pos`
  pasa a `eval="False"` (checkbox independiente en "Extra Rights", en vez
  de opción del dropdown exclusivo de PdV).

## Impact

- **Capability**: `pos-discount-authorized-group` (nueva).
- **Módulo**: `l10n_ve_pos` (`data/res_group.xml`).
- **Comportamiento del PdV**: ninguno — el grupo no está conectado a
  ninguna verificación de permisos todavía. El único efecto observable es
  en Ajustes → Usuarios: el grupo deja de competir por el mismo selector
  que "Usuario"/"Administrador" de Point of Sale.
- **Riesgo de despliegue**: bajo. Requiere `-u l10n_ve_pos` para que el
  `noupdate` de datos limpie el `privilege_id` existente en instalaciones
  ya desplegadas (quitar el `<field>` no basta, Odoo no borra valores
  omitidos en un upgrade).
