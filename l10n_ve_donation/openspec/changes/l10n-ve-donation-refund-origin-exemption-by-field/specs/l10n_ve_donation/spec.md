## ADDED Requirements

### Requirement: NC de donación exenta de la validación de origen por `is_donation`
Una Nota de Crédito con `is_donation` activo DEBE (MUST) quedar exenta de la validación de productos y montos contra la factura origen de `l10n_ve_invoice`, sin depender de ninguna clave de contexto, sobrescribiendo `_l10n_ve_skip_refund_origin_validation()`.

#### Scenario: NC de donación publicada a mano
- **WHEN** la Nota de Crédito automática de una factura de donación, que quedó en borrador, se publica en una llamada posterior sin la clave `l10n_ve_skip_refund_origin_validation`
- **THEN** se publica sin error, aunque su producto de donación no esté en la factura original

#### Scenario: La misma NC sin `is_donation`
- **WHEN** se publica una Nota de Crédito equivalente (producto de donación, monto mayor al facturado) con `is_donation` desactivado
- **THEN** el sistema rechaza la publicación con un `ValidationError` de `l10n_ve_invoice`
