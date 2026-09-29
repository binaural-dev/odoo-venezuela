## MODIFIED Requirements

### Requirement: Panel de estado de pago con desglose IGTF

Cuando alguna línea de pago usa un método `apply_igtf`, el panel de estado de la pantalla de pago DEBE (MUST) mostrar la base imponible (`bi_igtf`), el IGTF generado, su equivalente foráneo y el renglón fijo "TOTAL a Pagar con IGTF" calculado como total de factura más el porcentaje sobre la factura COMPLETA (`get_total_with_igtf`, valor de referencia que no varía con lo pagado). Bajo ese renglón DEBE (MUST) mostrarse además su equivalente en moneda foránea (`get_foreign_total_with_igtf`, expuesto a la plantilla como `foreignTotalWithIgtfAmount` y formateado con `formatForeignCurrency`), derivado como suma del total foráneo de factura (`get_foreign_total_with_tax`) más el IGTF foráneo de la factura completa, cada parte convertida una sola vez desde su contraparte local (misma regla anti-drift que `get_foreign_total_paid_with_igtf`). Además, cada línea de pago con `include_igtf` muestra su recargo en formato "local / foráneo".

#### Scenario: Método IGTF seleccionado

- **WHEN** el cajero agrega una línea con un método `apply_igtf`
- **THEN** aparece el bloque con BI IGTF, IGTF, Foreign IGTF y el total de referencia con IGTF, con su equivalente foráneo bajo el renglón "TOTAL a Pagar con IGTF"

#### Scenario: Total foráneo con IGTF coherente con el local

- **WHEN** el panel muestra el renglón "TOTAL a Pagar con IGTF" en moneda principal
- **THEN** el equivalente foráneo bajo él es la conversión de ese mismo total de referencia (factura completa + 3%), sin drift respecto a las partes foráneas que el cajero ya ve en pantalla
