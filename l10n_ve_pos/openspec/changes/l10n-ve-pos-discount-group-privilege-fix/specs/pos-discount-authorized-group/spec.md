# Spec delta: pos-discount-authorized-group

## ADDED Requirements

### Requirement: `group_authorized_discount_pos` es independiente del nivel de acceso base al PdV

`l10n_ve_pos.group_authorized_discount_pos` SHALL NOT tener `privilege_id`.
El sistema SHALL permitir que un usuario tenga cualquier combinación de
este grupo junto con `group_pos_user` o `group_pos_manager`
simultáneamente, en vez de competir por el mismo selector exclusivo de
"Point of Sale" en el formulario de usuario.

#### Scenario: Asignar el grupo sin perder el nivel de acceso base

- **GIVEN** un usuario con `group_pos_user` (o `group_pos_manager`)
- **WHEN** un administrador le marca el checkbox "Authorized discount pos"
  en Ajustes → Usuarios
- **THEN** el usuario conserva su nivel de acceso al PdV (Usuario/
  Administrador) Y el checkbox de "Authorized discount pos" queda
  marcado a la vez, sin reemplazar la selección anterior

### Requirement: El grupo no implica ninguna verificación de permisos en el numpad de descuento

Este change SHALL NOT añadir ninguna lectura de
`group_authorized_discount_pos` en `product_screen.js`, `res_users.py` ni
ningún otro punto del PdV. La autorización real de descuentos en el PdV
SHALL seguir resolviéndose por
`binaural_pos_hr.pos_discount_require_supervisor_key` (PIN/barcode vía
`SupervisorPopup`), documentado en la capability
`pos-hr-supervisor-authorization` de `binaural_pos_hr`.

#### Scenario: El grupo queda marcado pero no cambia el comportamiento del numpad

- **GIVEN** un usuario con el checkbox "Authorized discount pos" marcado
- **WHEN** usa el botón `%` del numpad en el PdV
- **THEN** el comportamiento es idéntico al de un usuario sin ese grupo —
  solo dependen de `pos.config.manual_discount`, el rol del cajero
  (core de Odoo) y, si está activo,
  `pos_discount_require_supervisor_key` (`binaural_pos_hr`)
