
## Why

El tipo de retención, el tipo de persona y el tipo de contribuyente del contacto (tarea #86944, y los tickets #16153 y #16339 que la anteceden) no estaban condicionados entre sí:

- Se podía guardar un contacto no residente como contribuyente especial, o una persona natural con un tipo de persona jurídica.
- El tipo de retención se ocultaba y se borraba a un proveedor PJ Ordinario o Formal usando `supplier_rank`, que no identifica a un proveedor nuevo, y su factura con retención de IVA fallaba con "The partner has no withholding type".
- Los no residentes quedaban sin tipo de retención aunque la retención de IVA sí se les practica al 100 %.

## What Changes

- `l10n_ve_payment_extension`: el tipo de persona se limita según `is_company`; PN Residente solo ofrece contribuyente ordinario y formal; los no residentes ocultan el contribuyente y no pueden ser especiales (`_check_non_resident_taxpayer_type`).
- `l10n_ve_payment_extension`: una sola regla, `_apply_default_withholding_type`, fija el tipo de retención por defecto: sin valor con contribuyente formal, 100 % para no residentes y PN Residente, 75 % para el resto de residentes. Un valor ya elegido se conserva y no se propone nada hasta elegir el tipo de persona.
- `l10n_ve_payment_extension`: la vista oculta el tipo de retención solo con contribuyente formal y lo exige para el especial residente y PN Residente.
- Cuatro campos calculados no almacenados en `res.partner`: `allowed_type_person_ids`, `is_non_resident_person`, `is_natural_resident_person` y `allowed_taxpayer_types`.
- Fuera de alcance: aplicar la regla a la creación por importación o API, el ajuste de compañía para activar la matriz solo en algunos clientes y la condición de la compañía Ordinaria de `binaural_validation_taxpayer_type`, que se eliminó en integra-addons#3300.

## Impact

- Specs afectadas: `l10n_ve_payment_extension` (tipo de persona según el contacto, tipo de contribuyente según el tipo de persona y tipo de retención por defecto).
- Versión de manifest: `l10n_ve_payment_extension` 19.0.2.2.10.
- Sin migración de datos: un contacto no residente que ya exista sin tipo de retención lo recibe al editar su tipo de persona o de contribuyente en el formulario.
- Validado por funcional (Andreína Tortolero) en la tarea 86944 el 19-11.
