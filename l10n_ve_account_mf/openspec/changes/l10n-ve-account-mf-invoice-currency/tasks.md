## 1. Implementación

- [x] 1.1 Líneas a la MF en la moneda de la compañía cuando la factura está en otra moneda (`_mf_build_company_invoice_lines`, `_mf_company_item`)
- [x] 1.2 Pagos a la MF en la moneda de la compañía (`_mf_build_company_payment_lines`)
- [x] 1.3 `toDriverOrder` pasa `discount_amount`
- [x] 1.4 Tests (`tests/test_mf_invoice_currency.py`, 8/8 en posv19)

## 2. Verificación

- [ ] 2.1 MF física: factura en USD con IVA incluido y excluido, pagada en $ y en Bs; NC
