
## Why

La revisión de Saul al PR 1657 (tareas #87829 y #86944) pidió cuatro cosas:

- El prefijo del RIF solo se restringía en pantalla: una importación o la API podían guardar un contacto persona con prefijo J.
- Una empresa nueva podía quedar con el prefijo V, y el contacto hijo de una empresa mostraba el número de la empresa con otro prefijo.
- La retención de un contacto hijo de una empresa fallaba con "The partner has no withholding type" o por falta de tipo de persona, porque el hijo no tiene información fiscal propia.
- En una venta el porcentaje de IVA se leía de la ficha del cliente, cuando funcional confirmó que lo define la condición de retención de la compañía.

## What Changes

- `l10n_ve_contact`: restricción en servidor `_check_prefix_vat_by_contact_type`: una empresa solo admite J, G o C y una persona V, E o P; el partner de una compañía de la base admite los seis; sin `vat` o sin prefijo no se valida.
- `l10n_ve_contact`: el prefijo por defecto sigue al registro (J en empresa, V en persona) con `_add_missing_default_values`, sin depender del contexto de la acción.
- `l10n_ve_contact`: el contacto hijo sigue la sincronización comercial estándar de Odoo (se copia el número, no el prefijo); no se agrega `prefix_vat` a `_commercial_fields`.
- `l10n_ve_payment_extension`: `account.move._get_iva_withholding_partner` devuelve la compañía en ventas y el contacto, o su empresa, en compras (`res.partner._get_retention_partner`). Lo usan `_create_retention`, el cálculo de líneas, el onchange de la línea y el reporte de líneas de retención.
- `l10n_ve_payment_extension`: el tipo de persona del ISLR de un contacto hijo se toma de su empresa en compras (`_get_islr_type_person_id`, `validate_islr`, validación del comprobante y TXT).
- Sin campos almacenados nuevos, sin override de `create`, `write` ni `unlink`, y sin copiar datos al contacto hijo.
- Fuera de alcance: corregir los tests de otros módulos que crean J sin `is_company` (acuerdo con Roque), el ISLR de venta y de `out_refund`, y copiar `condition_withholding_id` al crear la compañía.

## Impact

- Specs afectadas: `l10n_ve_contact` (prefijo por tipo de contacto y contacto hijo) y `l10n_ve_payment_extension` (fuente de la información fiscal de la retención).
- Versiones de manifest: `l10n_ve_contact` 19.0.1.9.1 y `l10n_ve_payment_extension` 19.0.2.2.11.
- Sin migración de datos: un contacto ya guardado con un prefijo que ahora no pasa la restricción solo se detecta al editarlo.
- Los tests de `l10n_ve_sale` e `l10n_ve_invoice_digital` que crean J sin `is_company` fallarán con la restricción.
- Una compañía sin `condition_withholding_id` no puede generar retenciones de IVA de venta hasta configurarla.
