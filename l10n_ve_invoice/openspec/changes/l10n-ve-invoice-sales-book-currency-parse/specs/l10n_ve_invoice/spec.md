## ADDED Requirements

### Requirement: Parseo correcto de importes formateados en el libro de compras/ventas
`convert_currency_to_float` DEBE (MUST) convertir a `float` los importes que el
libro toma ya formateados desde `move.tax_totals`, cualquiera sea la posición del
símbolo de moneda, incluyendo el formato de la localización venezolana `"Bs."`
seguido de un espacio no-separable (`\xa0`) y el monto en formato es_VE (punto de
miles, coma decimal). NO debe descartar el monto por quedarse con el lado del
símbolo al partir por el espacio no-separable.

#### Scenario: Símbolo antes del monto con espacio no-separable
- **WHEN** se convierte `"Bs.\xa0876,18"`
- **THEN** el resultado es `876.18` y no se registra ningún warning de conversión

#### Scenario: Miles y decimales en formato es_VE
- **WHEN** se convierte `"Bs.\xa02.382,11"`
- **THEN** el resultado es `2382.11`

#### Scenario: Símbolo después del monto
- **WHEN** se convierte `"1.234,56\xa0Bs."`
- **THEN** el resultado es `1234.56`

#### Scenario: Cadena vacía o no numérica
- **WHEN** se convierte `""`, `None` o `"ABC"`
- **THEN** el resultado es `0.0`
