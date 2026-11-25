## 1. l10n_ve_invoice — control de proveedor

- [x] 1.1 Duplicado de proveedor = proveedor + `name` + control, sobre todo el árbol de la matriz (`_get_repeated_vendor_bill`, con `sudo()`)
- [x] 1.2 `_check_correlative` también al cambiar `name`; `_check_vendor_correlative_before_post` valida al confirmar, también en lote
- [x] 1.3 Pruebas con `Form` R1 a R5, borradores, notas de crédito y regresión de ventas (`TestVendorCorrelativeWithRef`)
- [x] 1.4 Pruebas con `Form` en sucursales nativas: dentro de una sucursal, entre sucursales y usuario restringido (`TestVendorCorrelativeBranches`)

## 2. l10n_ve_invoice — secuencia de control

- [x] 2.1 `ir.sequence.check_sequence_exists` y `get_sequence` con la secuencia más antigua
- [x] 2.2 Pruebas con `Form`, incluida matriz y sucursal (`TestCorrelativeSequence`)

## 3. Restricciones de base de datos

- [x] 3.1 `l10n_ve_location` y `l10n_ve_payment_extension` pasan a `models.Constraint`, con traducción es_VE
- [x] 3.2 Pruebas con `Form` (`TestResCountryCityConstraints`, `TestSqlConstraints`)
- [x] 3.3 `l10n_ve_accountant`: se eliminan los `_sql_constraints` vacíos

## 4. Verificación

- [x] 4.1 Base limpia (`-i l10n_ve,l10n_ve_invoice,l10n_ve_location,l10n_ve_payment_extension --without-demo=all`) con los cinco tags: 41 pruebas, 0 fallos
- [ ] 4.2 Probar la creación de las restricciones sobre una copia de una base con duplicados
- [ ] 4.3 Decidir con el cliente cuál de las secuencias activas duplicadas se conserva
