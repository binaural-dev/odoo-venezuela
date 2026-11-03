# Fix: fecha del asiento de diferencial alterno standalone alineada con el nativo

## Why

Ticket #16196 (https://binaural.odoo.com/odoo/helpdesk/action-389/16196). Una
factura de proveedor en USD (FP-DF-0002) pagada en tres fracciones con fechas
distintas, conciliada de nuevo el 27 oct, dejó los tres asientos CAMBIO fechados
el 27 oct, y el ticket pide (R1) fecharlos el día de cada pago.

## Hallazgos (probados con tests `Form`, toggle alterno ON y OFF)

1. **El caso reportado (factura USD) no pasa por el diferencial alterno.** La
   exposición en USD ya está fija, el alterno no inyecta montos y el CAMBIO es
   100% nativo. Con el toggle ON u OFF las fechas son idénticas.
2. **La fecha la fija el core, no este módulo.** El core fecha su asiento de
   diferencial con `journal.accounting_date` (`_get_accounting_date`), regla que
   mantiene crecientes numeración y fecha del diario CAMBIO. Si cada pago se
   concilia el día de su fecha, el CAMBIO sale con la fecha del pago. Al
   re-conciliar después, el core lo corre a fin de mes (secuencia mensual) o a
   "hoy" (secuencia anual). El informe (27 oct en los tres) encaja con la anual;
   no verificado en la BD del cliente.
3. **Desalineo real corregido:** el asiento alterno *standalone* (factura en Bs
   pagada en USD, sin asiento nativo) se fechaba con `max(debit.date, credit.date)`
   crudo, ignorando la regla del core. Ahora usa la misma
   (`journal.with_context(move_date=...).accounting_date`), así nativo y alterno
   de una misma conciliación se fechan igual.

## Fuera de alcance / decisión funcional pendiente

R1 (cada CAMBIO con la fecha de su pago aun en re-conciliación tardía) no se
cumple, ni en el nativo ni en el alterno. Cumplirlo implica saltarse la regla de
secuencia del core y afectaría también al diferencial nativo.

## Impacto

El asiento standalone ahora requiere tasa en la fecha ajustada (p. ej. fin de
mes), igual que el nativo; sin ella, la conciliación lanza "no rate assigned".
