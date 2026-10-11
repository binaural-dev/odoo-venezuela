## ADDED Requirements

### Requirement: Documento fiscal en la moneda de la compañía para facturas en otra moneda
El documento que se envía a la máquina fiscal desde Contabilidad para una factura en una moneda distinta a la de la compañía SHALL ir en la moneda de la compañía, con cada línea por su monto en el asiento (base si el impuesto es excluido, total con IVA si es incluido); las facturas en la moneda de la compañía no cambian.

#### Scenario: Impuesto excluido
- **WHEN** se imprime una factura en USD de 5 × $ 2,32 con IVA 16 % excluido y tasa 803,34
- **THEN** la MF recibe 5 × 1.863,75 con un descuento por monto de 0,01 sobre el ítem
- **AND** la base impresa (9.318,74) es igual a la del asiento

#### Scenario: Impuesto incluido
- **WHEN** se imprime una factura en USD de 1 × $ 12,45 con IVA 16 % incluido y tasa 803,34
- **THEN** la MF recibe el total con IVA en Bs (10.001,58), no la base

#### Scenario: Pagos
- **WHEN** la factura en USD está pagada completa
- **THEN** los pagos llegan en la moneda de la compañía a la tasa de la factura y suman el total de la factura
- **AND** la diferencia en cambio no se envía como pago

#### Scenario: Factura en la moneda de la compañía
- **WHEN** se imprime una factura en Bs
- **THEN** el documento se arma igual que antes
