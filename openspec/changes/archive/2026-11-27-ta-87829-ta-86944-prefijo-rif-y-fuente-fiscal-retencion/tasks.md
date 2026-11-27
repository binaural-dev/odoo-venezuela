## 1. Prefijo del RIF

- [x] 1.1 Validar el prefijo según el tipo de contacto con `_check_prefix_vat_by_contact_type`.
- [x] 1.2 Fijar el prefijo por defecto según el registro en `_add_missing_default_values`.
- [x] 1.3 Dejar el contacto hijo con la sincronización estándar de Odoo (número sí, prefijo no).

## 2. Fuente fiscal de la retención

- [x] 2.1 Resolver el partner fiscal del IVA con `_get_iva_withholding_partner` (compañía en ventas, contacto o su empresa en compras).
- [x] 2.2 Usar la empresa del contacto hijo para el tipo de persona del ISLR.
- [x] 2.3 Aplicar la misma regla en el reporte de líneas de retención.

## 3. Pruebas y versión

- [x] 3.1 Tests del prefijo en servidor y del defecto según el contexto.
- [x] 3.2 Tests de IVA e ISLR de un contacto hijo y del IVA de venta desde la compañía.
- [x] 3.3 Subir `l10n_ve_contact` a 19.0.1.9.1 y `l10n_ve_payment_extension` a 19.0.2.2.11.
