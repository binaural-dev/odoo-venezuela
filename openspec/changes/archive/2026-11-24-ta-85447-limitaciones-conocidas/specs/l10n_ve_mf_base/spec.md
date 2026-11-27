## MODIFIED Requirements

### Requirement: Resultado verificado del documento fiscal

`printInvoice`, `printCreditNote` y `printDebitNote` DEBEN (MUST) tomar una foto de S1 (número, subtotal de ventas, Z y serial) antes de abrir el documento, si la máquina está en reposo. Un éxito NO DEBE (MUST NOT) cambiar. Si la impresión falla después de enviar un pago, DEBEN (MUST) consultar a la máquina y devolver `printed: true` con el número, `printed: false` (no emitido o anulado) o `printed: null` con la verificación.

#### Scenario: Factura exitosa

- **WHEN** la factura se imprime sin errores
- **THEN** el resultado es el mismo de siempre, sin `printed`, y la única diferencia en la secuencia es la lectura S1 previa

#### Scenario: Pago registrado reportado como fallido

- **GIVEN** que un comando falla después del primer pago y el driver manda `7`
- **WHEN** S1 muestra el número siguiente y el subtotal de ventas aumentó
- **THEN** el resultado es `success: true, printed: true, recovered: true` con ese número

#### Scenario: Máquina en reposo sin foto

- **WHEN** la máquina no está en reposo al empezar o S1 no responde
- **THEN** no hay foto y el resultado es el de siempre

#### Scenario: Falla después de un pago sin foto (riesgo aceptado)

- **GIVEN** que no hubo foto porque la máquina no estaba en reposo al empezar o S1 no respondió
- **WHEN** la impresión falla después de enviar un pago
- **THEN** el resultado es el de siempre, sin `printed`, y el PdV deja el pedido pendiente: sin foto no hay contra qué verificarlo
