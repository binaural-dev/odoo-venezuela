## 1. Tipo de persona y de contribuyente

- [x] 1.1 Limitar `type_person_id` según `is_company` con `allowed_type_person_ids` y vaciarlo al cambiar de persona a compañía.
- [x] 1.2 Ofrecer solo `ordinary` y `formal` a PN Residente con `allowed_taxpayer_types` y el widget `filterable_selection`.
- [x] 1.3 Ocultar el contribuyente de los no residentes y rechazar `special` con `_check_non_resident_taxpayer_type`.

## 2. Tipo de retención

- [x] 2.1 Decidir el valor por defecto en `_apply_default_withholding_type` (formal vacío, no residente y PN Residente 100 %, resto 75 %).
- [x] 2.2 Conservar el valor elegido y no proponer nada hasta elegir el tipo de persona.
- [x] 2.3 Ocultar el campo solo con contribuyente formal y exigirlo para especial residente y PN Residente.

## 3. Pruebas y versión

- [x] 3.1 Pruebas del formulario del contacto (`foreign_supplier_required_fields`) y de la factura de compra con retención de IVA (`retention_iva_partner_default`).
- [x] 3.2 Subir `l10n_ve_payment_extension` a 19.0.2.2.10.
