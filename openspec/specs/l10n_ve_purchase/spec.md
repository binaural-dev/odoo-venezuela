# l10n_ve_purchase

## Purpose

Módulo mínimo del vertical de compras venezolano. Su único contenido funcional es un ajuste de permisos: redefine la ACL `purchase.access_account_move` para dar al grupo de usuarios de compras acceso completo a los asientos contables. Depende de `purchase` y `account`. No define modelos, vistas ni datos propios.

## Requirements

### Requirement: Acceso completo de usuarios de compras a asientos contables

El módulo DEBE (MUST) redefinir la ACL `purchase.access_account_move` sobre `account.move` para el grupo `purchase.group_purchase_user` con permisos de lectura, escritura, creación y eliminación (`perm_read`, `perm_write`, `perm_create`, `perm_unlink` en 1).

#### Scenario: Usuario de compras opera facturas de proveedor

- **WHEN** un usuario con el grupo de usuario de compras accede a registros de `account.move`
- **THEN** puede leerlos, modificarlos, crearlos y eliminarlos sin requerir grupos contables adicionales
