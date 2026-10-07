## 1. l10n_ve_stock — el combo queda exento del impuesto único

- [x] 1.1 `_validate_single_sale_tax` filtra los productos `type == "combo"` antes de contar impuestos por compañía
- [x] 1.2 Bump del manifest 19.0.1.0.8 → 19.0.1.0.9

## 2. Verificación

- [x] 2.1 BD limpia con `l10n_ve_pos` + `l10n_ve_accountant` (como el CI en integración): `TestProductTemplate` pasa de 4 errores a 30/30 en verde
- [x] 2.2 Sin regresión en `/l10n_ve_stock`: 155/155 en verde junto con `TestProductTemplate`
