# l10n_ve_purchase

## Purpose

Módulo base del vertical de compras venezolano. En 20 no tiene contenido funcional propio: no define modelos, vistas, datos ni permisos. Se conserva como dependencia común de los módulos de compras que se apoyan en él: en integra-addons, `binaural_purchase` y `binaural_foreign_cost` (migrados a 20) y `binaural_integration_h` (todavía sin migrar). Depende de `purchase` y `account`.

En 19 su único contenido era redefinir la ACL `purchase.access_account_move`, para que el usuario de compras pudiera leer, crear, modificar y borrar facturas sin grupos contables. En 20 ese id ya no existe y el módulo `purchase` de Odoo da por su cuenta al grupo `purchase.group_purchase_user` permiso completo sobre `account.move` en los documentos de proveedor (`in_invoice`, `in_refund`, `in_receipt`, regla `purchase_user_account_move_rule`), y crear, leer y modificar sus líneas. Por eso el módulo quitó su archivo de permisos. Ese permiso es del núcleo, no de este módulo, y no se describe como requisito aquí.

## Requirements

### Requirement: Sin permisos propios

El módulo NO DEBE (MUST NOT) crear ni redefinir reglas de acceso (`ir.access`) ni reglas de registro: los permisos del usuario de compras sobre las facturas de proveedor DEBEN (MUST) ser los que da el módulo `purchase` de Odoo, con o sin `l10n_ve_purchase` instalado.

#### Scenario: Instalación del módulo

- **WHEN** se instala `l10n_ve_purchase`
- **THEN** no se agrega ni cambia ninguna regla de acceso, y el usuario de compras tiene sobre las facturas de proveedor los mismos permisos que en una base sin el módulo

### Requirement: Base de los módulos de compras

El módulo DEBE (MUST) seguir siendo instalable y sin datos propios, para que los módulos que lo declaran como dependencia (`binaural_purchase`, `binaural_foreign_cost` y, cuando se migre, `binaural_integration_h`) se instalen sin cambios en su manifiesto.

#### Scenario: Instalar un módulo que depende de él

- **WHEN** se instala `binaural_purchase` en una base de 20
- **THEN** `l10n_ve_purchase` se instala como dependencia y no aporta datos ni permisos
