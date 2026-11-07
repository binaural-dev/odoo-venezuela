## 1. Implementación

- [x] 1.1 `_get_retention_iva_domain()` en `wizard.retention.iva` con `in_invoice` e `in_refund`
- [x] 1.2 `generate_txt` y `download_retention_iva_txt` usan ese dominio
- [x] 1.3 Quitar la asignación duplicada de "Número del documento afectado" (ND sin origen daba `False`)
- [x] 1.4 Número de control vacío como cadena vacía (antes `TypeError` en la descarga)
- [x] 1.5 Versión del manifest 19.0.2.2.6
- [x] 1.6 Archivar el change y volcarlo en `openspec/specs/l10n_ve_payment_extension/spec.md`

## 2. Tests

- [x] 2.1 `tests/test_retention_iva_txt_refunds.py` (flujo de usuario con `Form`: factura, nota de crédito por el
      asistente de reversión, retención, wizard y controlador): línea de la NC con tipo `03`, afectado y montos en
      positivo; solo NC no da error; TXT con factura y NC; facturas sin cambios; mismo dominio en conteo y descarga;
      ND con origen (`02`) y sin origen (`0`); NC sin número de control
      (`odoo --test-tags /l10n_ve_payment_extension:TestRetentionIvaTxtRefunds`: 9 en verde, más los 7 de
      `TestRetentionIvaWizard`)
- [x] 2.2 Suite completa de `l10n_ve_payment_extension`: 551 tests, 0 fallos
