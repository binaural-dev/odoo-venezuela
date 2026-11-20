## Why

La conciliación manual nativa de Enterprise (botón Reconciliar de los apuntes por conciliar) concilia con el motor del core y se salta lo que `l10n_ve_igtf` añade al widget de pagos de la factura: el cruce de anticipo, el IGTF y las tasas del widget. Un pago o anticipo conciliado a mano no da el mismo resultado que el aplicado desde la factura.

## What Changes

- Nuevo `l10n_ve_reconcile_assistant`: clasifica la selección y, si es un pago o anticipo contra una o varias facturas, abre un asistente con una vista previa sin escritura (monto, fecha de conversión, tasa, IGTF, saldo del origen antes y después). Las facturas se reordenan arrastrando y al confirmar se aplica par por par con `js_assign_outstanding_line`, en una sola transacción.
- Nuevo `l10n_ve_reconcile_assistant_accountant` (`auto_install`): sustituye `account.move.line.action_reconcile` para abrir el asistente.
- Bloquea con explicación los cruces, las notas, el anticipo contra otra cuenta, los socios o compañías distintos y más de un origen.
- El residual que deja un pago hecho de más desde la factura ("RESTANTE DE PAGO EN DIVISA") es un anticipo válido: se clasifica por la línea y no por `is_advance_move`, que también marca los cruces.
- La vista previa de un anticipo imita `_create_advance_payment_move`, que consume `saldo × base ÷ monto del widget` con montos redondeados; el saldo previsto coincide con el real.

## Non-goals

- No cambia `l10n_ve_igtf`. La diferencia de centavos que produce la fórmula del cruce de anticipo es comportamiento previo y se corrige aparte.
- No concilia varios orígenes a la vez ni líneas de retención.
- La sucursal analítica vive en integra-addons (`binaural_subsidiary_reconcile_assistant`).

## Impact

- Módulos nuevos: `l10n_ve_reconcile_assistant` 19.0.1.0.0 y `l10n_ve_reconcile_assistant_accountant` 19.0.1.0.0.
- Specs: `l10n_ve_reconcile_assistant` y `l10n_ve_reconcile_assistant_accountant`.
