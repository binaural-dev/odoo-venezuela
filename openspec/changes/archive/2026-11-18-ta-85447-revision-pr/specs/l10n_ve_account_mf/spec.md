## ADDED Requirements

### Requirement: Documento de un pedido del PdV por verificar

`check_print_out_invoice()` y `check_print_out_refund()` DEBEN (MUST) rechazar con `ValidationError`, antes de las demás validaciones de impresión, el documento cuyo `pos.order` tiene `mf_print_verification`: no se sabe si la máquina ya lo emitió, e imprimirlo podría duplicarlo. El mensaje DEBE (MUST) nombrar el pedido. Sin `l10n_ve_pos_mf` instalado (sin el campo) no se comprueba nada.

#### Scenario: Factura de un pedido por verificar

- **GIVEN** una factura publicada sin número fiscal cuyo pedido del PdV está por verificar
- **WHEN** se intenta imprimirla desde el formulario de la factura
- **THEN** se lanza un error que nombra el pedido y no se envía nada a la máquina

#### Scenario: Nota de crédito de un pedido por verificar

- **WHEN** se intenta imprimir la nota de crédito de un pedido del PdV por verificar
- **THEN** se lanza el mismo error

#### Scenario: Pedido ya resuelto

- **GIVEN** que el pedido se resolvió como "no emitido"
- **WHEN** se intenta imprimir su factura
- **THEN** se aplican las validaciones de siempre
