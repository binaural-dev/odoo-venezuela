## 1. Implementación

- [x] 1.1 Merge de 19.0: `l10n_ve_pos_mf/__manifest__.py` en 19.0.3.3.0 y `es_VE.po` con las dos partes
- [x] 1.2 `_documentOutcome`: NC/ND releen el estado después del `7` (`_statusAfterAbort`); fuera de reposo `document_open`, sin respuesta `no_response`
- [x] 1.3 `pos.order._mf_check_fiscal_number`, usado por el asistente y por `mf_resolve_print_verification`
- [x] 1.4 `mf_resolve_print_verification` responde `manual_review`, deja la marca y el chatter si el número no puede ser del pedido
- [x] 1.5 `PosStore._mfApplyPrintVerification`: con `manual_review` restaura la orden local, saca la entrada y avisa
- [x] 1.6 Traducciones es_VE

## 2. Pruebas

- [x] 2.1 Hoot (`l10n_ve_mf_base`): NC y ND que siguen abiertas después del ACK del `7`; NC que el `7` deja en reposo (mismo número y siguiente); NC muda después del `7`; factura abierta después del ACK del `7` sin cambios
- [x] 2.2 Hoot (`l10n_ve_pos_mf`): número rechazado por el servidor al resolver antes de imprimir, y al volver a validar
- [x] 2.3 Python (`l10n_ve_pos_mf`): resolución con el número de otro pedido, de otra máquina, anterior a la foto y sin serial; lo que no escribe sigue igual

## 3. Verificación (2026-11-23, sobre el merge de 19.0)

- [x] 3.1 Python en base nueva, `l10n_ve_pos_mf` solo (como el CI): 0 fallos, 0 errores de 50
- [x] 3.2 Python en base nueva, `l10n_ve_pos_mf,l10n_ve_pos_igtf,l10n_ve_account_mf`: 0 fallos, 0 errores de 56
- [x] 3.3 Hoot `@l10n_ve_mf_base`: 71 pasan, 0 fallan
- [x] 3.4 Hoot `@l10n_ve_pos_mf`: 37 pasan, 0 fallan (`fiscal_payment_validation` 30). En la misma corrida fallan 10 de
      `@l10n_ve_pos/unit/pos_order_line_discount`, módulo que este PR no toca; fallan igual en otras ramas
