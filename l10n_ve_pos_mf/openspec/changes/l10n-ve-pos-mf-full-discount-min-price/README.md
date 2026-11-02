# l10n-ve-pos-mf-full-discount-min-price

Evita facturar en Bs 0,00 en el PdV con máquina fiscal cuando se aplica un
descuento del 100% (por línea o global). Al detectar que el descuento dejaría
el neto de una línea en 0, se sustituye por precio unitario **0,01 sin
descuento**: la MF (que no acepta líneas en 0,00) imprime la línea, la factura
no se bloquea por `_check_max_discount` (descuento < 100%), y total, pago y
factura quedan consistentes en 0,01. Ticket #15105.
