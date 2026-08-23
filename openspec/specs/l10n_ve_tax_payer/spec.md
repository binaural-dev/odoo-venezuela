# l10n_ve_tax_payer

## Purpose

Módulo técnico que agrega la clasificación de contribuyente venezolano a los contactos. Extiende `res.partner`. Depende de `base`, `l10n_ve_rate` y `l10n_ve_accountant`. Otros módulos de la localización (como `l10n_ve_invoice` y `l10n_ve_payment_extension`, que lo declara como dependencia) consumen el campo `taxpayer_type` para lógica de períodos fiscales y retenciones.

## Requirements

### Requirement: Tipo de contribuyente en el contacto

Todo contacto (`res.partner`) DEBE (MUST) tener un tipo de contribuyente en el campo `taxpayer_type` (Selection con opciones `formal` "Formal", `special` "Special" y `ordinary` "Ordinary"), con valor por defecto `ordinary`, marcado como obligatorio en el formulario de contacto y con seguimiento (`tracking`) de sus cambios en el chatter.

#### Scenario: Contacto nuevo sin especificar tipo

- **WHEN** se crea un contacto sin indicar `taxpayer_type`
- **THEN** el contacto queda con tipo de contribuyente `ordinary`

#### Scenario: Cambio de tipo de contribuyente

- **WHEN** un usuario cambia el `taxpayer_type` de un contacto (por ejemplo de `ordinary` a `special`)
- **THEN** el cambio se registra en el chatter del contacto por el tracking del campo
