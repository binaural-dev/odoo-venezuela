## ADDED Requirements

### Requirement: "Permitir crear productos" por caja

`pos.config` DEBE (MUST) tener `allow_product_creation_in_pos` ("Permitir crear productos"), apagado por defecto y editable desde Ajustes. Apagado, el PdV DEBE (MUST) ocultar "Crear producto" del menú y "Crear manualmente" de la pantalla de productos vacía, y `PosStore.editProduct()` sin producto NO DEBE (MUST NOT) abrir el formulario. Solo un `true` explícito la enciende.

#### Scenario: Creación permitida

- **WHEN** la caja tiene "Permitir crear productos" encendido y el usuario tiene permiso para crear productos
- **THEN** el menú del PdV muestra "Crear producto" y abre el formulario de producto nuevo

#### Scenario: Creación apagada

- **WHEN** la caja tiene "Permitir crear productos" apagado
- **THEN** el menú no muestra "Crear producto", la pantalla de productos vacía no muestra "Crear manualmente" y `editProduct()` sin producto no abre nada

#### Scenario: Editar un producto existente con la creación apagada

- **WHEN** la caja tiene "Permitir crear productos" apagado y el cajero edita un producto existente
- **THEN** se abre el formulario de edición como siempre

#### Scenario: Caja cargada antes de actualizar el módulo

- **WHEN** el PdV trae `pos.config` de su caché sin el campo (`undefined`)
- **THEN** la creación se trata como no permitida

#### Scenario: Cajas existentes al actualizar

- **WHEN** se actualiza `l10n_ve_pos` en una base con cajas creadas antes
- **THEN** todas quedan con "Permitir crear productos" apagado hasta que se encienda en Ajustes
