## Why

Al instalar o actualizar `l10n_ve_accountant`, `_auto_init` renombraba con un sufijo ` (n)` las facturas de proveedor publicadas que compartían número, proveedor y diario, para poder crear el índice único ampliado. Facturas correctas (por ejemplo, las traídas en una migración de datos) terminaban con un número distinto al real (ticket 14986). En 17.0 se corrigió con binaural-dev/odoo-venezuela#1271; 19.0 seguía renombrando.

Además, en 19 el core declara ese índice como table object (`account.move._unique_name`, `UniqueIndex` sobre `(name, journal_id)`). La implementación anterior lo reemplazaba a mano y dependía de que el ORM conserve un índice sin comentario; si el índice volvía a ser el estrecho con comentario (soporte, `-u account`), nadie lo corregía, porque solo se miraba si existía el marcador `account_move_unique_name_ve`.

## What Changes

- `account.move` redeclara `_unique_name` como `UniqueIndex` sobre `(name, partner_id, company_id, journal_id)` para asientos publicados con nombre distinto de `/`. El ORM reemplaza el índice del core porque su definición difiere.
- `_auto_init`, mientras el índice de la base no sea el ampliado: busca asientos publicados con el mismo número, proveedor, diario y compañía y, si los hay, detiene la instalación con un `UserError` que lista hasta 20 casos (proveedor, diario, número, cantidad). No modifica ningún dato. Sin duplicados, borra el índice estrecho (también uno sin comentario, que el ORM conservaría) y deja que el ORM cree el ampliado.
- Se borra el marcador `account_move_unique_name_ve` de la implementación anterior.
- Pruebas: `tests/test_account_move_unique_name_index.py` (6 casos).

## Impact

- **Specs afectadas**: `l10n_ve_accountant` (unicidad del nombre del asiento).
- **Código**: `models/account_move.py`, `i18n/es_VE.po`. Sin migración.
- **Qué ve el usuario**: si la base tiene números duplicados por proveedor/diario/compañía, la instalación o actualización se detiene con la lista de casos en vez de renombrarlos. El mensaje sale en inglés: durante la carga de modelos el entorno no tiene idioma.
- **Datos existentes**: las facturas que ya fueron renombradas por la versión anterior conservan el sufijo; este cambio no las recupera.
