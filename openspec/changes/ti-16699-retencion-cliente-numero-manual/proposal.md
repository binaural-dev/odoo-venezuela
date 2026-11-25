## Why

Al publicar una factura de cliente con «¿Genera retención de IVA?» marcado, el sistema crea la retención de cliente en borrador y le asigna un número de la secuencia `retention.iva.control.number`, que es la secuencia fiscal de los comprobantes que la empresa emite a sus proveedores. Además copia ese número en `iva_voucher_number` de la factura.

En una venta el agente de retención es el cliente: él emite el comprobante y el número llega después. Tomarlo de nuestra secuencia deja huecos en el correlativo fiscal de los comprobantes a proveedores. Evidencia (staging de La Giralda, 2026-11-24): retenciones de proveedor 20261100000006 a 20261100000012; las retenciones de cliente en borrador de F000021 a F000023 tomaron 20261100000013 a 20261100000015, y el siguiente comprobante a un proveedor saldría con el 16.

Causas:

1. `account_move.py` → `action_post` crea la retención IVA y hace `move.iva_voucher_number = retention.number` sin distinguir factura de cliente y de proveedor.
2. `account_retention.py` → `create` → `_set_sequence` numera todo comprobante sin `number`, sin mirar el tipo. Afecta también a ISLR y municipal de cliente.
3. Los formularios IVA, ISLR y municipal exigían el número (`required="type == 'out_invoice'"`), así que el borrador sin número no se podía guardar.

## What Changes

- `_set_sequence` NO numera los comprobantes de cliente (`out_invoice`, `out_refund`, `out_debit`, `out_contingence`): el número lo escribe el usuario. Los de proveedor siguen numerándose igual.
- `action_post` de `account.move`: en factura de cliente la retención IVA se crea en borrador sin número y `iva_voucher_number` no se llena; se llena al emitir la retención con el número real (`set_voucher_number_in_invoice`). Mientras exista una retención IVA (o ISLR) no cancelada de la factura no se crea otra al volver a publicar, porque el campo `*_voucher_number` ya no sirve de guarda.
- Los tres formularios dejan de exigir el número en borrador. Al emitir, `action_post` sigue exigiéndolo («Insert a number for the retention») y el IVA, los 14 dígitos.
- Pruebas: `test_customer_iva_retention_no_sequence.py` (8 casos) y cinco aserciones existentes que asumían el número automático en el borrador de cliente (`test_withholdings_iva_partner`, `test_withholdings_islr`).

## Impact

- **Specs afectadas**: `l10n_ve_payment_extension` (numeración automática, número obligatorio en retenciones de cliente, generación automática al publicar la factura).
- **Código**: `models/account_move.py`, `models/account_retention.py`, `views/account_retention_{iva,islr,municipal}.xml`. Sin migración ni textos nuevos.
- **Qué ve el usuario**: el borrador de retención de cliente aparece sin número («/») y la factura sin comprobante hasta que se escribe el número del cliente y se emite; la secuencia de proveedores deja de saltar.
- **Lo que no cambia**: numeración de proveedores, emisión automática de `in_invoice`, validaciones de monto y formato.
- **Datos existentes**: las retenciones de cliente en borrador ya numeradas conservan su número; los huecos ya consumidos de la secuencia no se recuperan.
- **Nota**: el monto de la retención de cliente también se escribe a mano (`auto_fill_retention_amount_iva` desactivado por defecto) y su validación va antes que la del número.
