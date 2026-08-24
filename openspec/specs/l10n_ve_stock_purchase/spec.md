# l10n_ve_stock_purchase

## Purpose

Ajuste de seguridad sobre el cruce inventario/compras: restringe los permisos que el módulo estándar `purchase_stock` otorga a los usuarios de compras sobre los traslados de inventario. No agrega modelos, vistas ni código Python; su único contenido es la sobreescritura de ACLs en `security/ir.model.access.csv`. Su única dependencia declarada es `purchase_stock` (no depende de `l10n_ve_stock`), y cumple el mismo propósito que el bloqueo de eliminación que `l10n_ve_stock` aplica a los grupos de inventario.

## Requirements

### Requirement: Eliminación de traslados bloqueada para usuarios de compras

El módulo DEBE (MUST) sobreescribir las ACL estándar `purchase_stock.access_stock_picking_purchase_user_manager` y `purchase_stock.access_stock_picking_purchase_user` dejando `perm_unlink` en 0, de modo que los usuarios de los grupos `purchase.group_purchase_manager` y `purchase.group_purchase_user` conserven lectura, escritura y creación sobre `stock.picking` pero no puedan eliminar traslados.

#### Scenario: Gerente de compras intenta eliminar un traslado

- **WHEN** un usuario del grupo `purchase.group_purchase_manager` intenta eliminar un registro de `stock.picking`
- **THEN** el sistema niega la operación por falta de permiso de eliminación

#### Scenario: Usuario de compras crea y edita traslados

- **WHEN** un usuario del grupo `purchase.group_purchase_user` crea o modifica un traslado
- **THEN** la operación se permite normalmente
