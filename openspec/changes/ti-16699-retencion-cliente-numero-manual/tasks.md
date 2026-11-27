## 1. l10n_ve_payment_extension — número manual en retenciones de cliente

- [x] 1.1 `models/account_retention.py`: `_set_sequence` omite los tipos `out_*`
- [x] 1.2 `models/account_move.py`: la factura de cliente crea el borrador IVA sin número ni `iva_voucher_number`; guarda contra duplicados para IVA e ISLR
- [x] 1.3 `views/account_retention_{iva,islr,municipal}.xml`: el número deja de ser obligatorio en borrador
- [x] 1.4 `tests/test_customer_iva_retention_no_sequence.py` y ajuste de las aserciones previas de `test_withholdings_iva_partner` y `test_withholdings_islr`

## 2. Verificación

- [x] 2.1 Las pruebas nuevas fallan sin el cambio (IVA: 3 de 4)
- [x] 2.2 Suite completa de `l10n_ve_payment_extension` en base limpia con `l10n_ve`
- [ ] 2.3 Revisar en el formulario: publicar factura de cliente con retención IVA, ISLR y municipal, guardar el borrador sin número, y emitir con y sin número
