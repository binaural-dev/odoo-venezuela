# Restringir `transfer_ids` al grupo de Inventario (l10n_ve_stock_account)

## Why

El campo `transfer_ids` de `account.move` (relación Many2many con
`stock.picking`, etiqueta "Transfers") quedaba visible para cualquier usuario
interno, incluidos los usuarios de facturación que no operan inventario. Es un
dato de stock: expone los traslados que originaron una factura y no aporta nada
a un usuario puramente contable.

Hasta ahora la restricción se aplicaba desde un módulo puente de
`integra-addons` (`binaural_l10n_ve_stock_account_access`), que ponía
`groups="stock.group_stock_user"` en el campo. Ese puente se elimina, así que la
restricción debe vivir en el módulo dueño del campo, `l10n_ve_stock_account`.

## What Changes

- **`models/account_move.py`**: `transfer_ids` pasa a declararse con
  `groups="stock.group_stock_user"`. No cambia el tipo, ni el modelo destino, ni
  la lógica que lo rellena desde los traslados.
- **`__manifest__.py`**: versión `19.0.2.1.4` → `19.0.2.1.5`.
- **Tests** (`tests/test_transfer_ids_group.py`):
  - un usuario de facturación **sin** el grupo de inventario no ve el campo en
    `fields_get(["transfer_ids"])`, y puede leer la factura sin `AccessError`;
  - un usuario **con** `stock.group_stock_user` sí lo ve.
  Usa `TransactionCase` de Odoo 19, sin mocks del ORM.

## Por qué el grupo existente y no uno nuevo

- `stock.group_stock_user` es el grupo que ya protege los pickings, es decir,
  el mismo dato que `transfer_ids` expone. Restringir con él mantiene
  coherencia: quien puede ver traslados puede ver los traslados de una factura;
  quien no, no.
- Uno de los grupos propios del módulo, `l10n_ve_stock_account.group_stock_account`
  ("Ver botón Crear Factura"), controla únicamente la visibilidad de un botón en
  el picking. No representa acceso a datos de inventario y ampliarlo a este
  campo mezclaría dos responsabilidades distintas.
- Crear un grupo nuevo solo para este campo añadiría configuración y mantenimiento
  sin una necesidad funcional: el grupo de Inventario ya expresa exactamente la
  audiencia correcta.

## Por qué no afecta a comisiones

Los grupos de comisiones (`binaural_clinics_commission`) son un eje distinto y
no tocan `transfer_ids` ni la visibilidad de campos de `account.move`. Esta
propuesta no modifica esos grupos ni su lógica; solo restringe un campo de stock
a los usuarios de inventario.

## Impact

- **Módulo**: `l10n_ve_stock_account` (localización venezolana, no `core`).
- **Usuarios**: quienes tienen `stock.group_stock_user` no notan cambios; quienes
  no lo tienen dejan de ver `transfer_ids` en formularios, listas y
  `fields_get`. No se rompe la lectura de la factura.
- **Dependencias**: no se agregan dependencias; `stock` ya es dependencia
  transitiva y `stock.group_stock_user` está disponible.
- **Migración de datos**: ninguna.
