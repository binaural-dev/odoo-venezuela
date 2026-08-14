# Tasks

## 1. Diagnóstico

- [x] 1.1 Rastrear el 0/0 de la sesión 00044 hasta `pos.payment.foreign_amount`
      en sí (pago "Efectivo Bs" que salda IGTF, comparado contra
      `foreign_igtf_amount` del pago hermano)
- [x] 1.2 Confirmar que ya estaba documentado como pendiente
      (`migration-lessons.md`, "Pendientes por tratar (2026-07-10)")
- [x] 1.3 Mapear TODOS los consumidores de `payment.foreign_amount`
      (agente Explore): los 4 de la nota original + `pos_session.py`
      (no listado antes, el mayor consumidor) + `payment_report_pos.py` +
      usos de solo-lectura en vistas/popup de reembolso
- [x] 1.4 Confirmar que ningún consumidor hace resta/división que asuma 0
      (todos son asignación directa sobre líneas ya identificadas por
      importe) — sin riesgo de doble conteo
- [x] 1.5 Confirmar que ningún test (Python ni JS) depende de la
      invariante vieja

## 2. Implementación

- [x] 2.1 `payment_model.js::_recomputeForeignFromLocal`: eliminar el gate
      `is_foreign_currency`, calcular siempre `localToForeign(amount)`
- [x] 2.2 Eliminar `_isForeignMethod()` (sin uso tras 2.1)
- [x] 2.3 Verificar sintaxis (`node --check`)

## 3. Tests

- [x] 3.1 `payment_model.test.js`: nuevo `describe` para
      `_recomputeForeignFromLocal` (método local, método foráneo, sin
      orden/sin helper)
- [ ] 3.2 Correr la suite de tests unitarios JS del PdV en el navegador —
      pendiente, no ejecutado en este pase
- [ ] 3.3 Correr la suite de tests Python de `l10n_ve_pos` /
      `l10n_ve_pos_igtf` en el contenedor `proj` — pendiente

## 4. Pendiente (fuera de alcance de este change, con seguimiento)

- [ ] 4.1 Data-fix de los asientos ya generados con `foreign_debit`/
      `foreign_credit = 0` en las sesiones 00043 y 00044
- [ ] 4.2 Auditar otras sesiones cerradas antes de este fix con el mismo
      patrón (pagos en método local con recargo IGTF o venta directa en Bs)
- [ ] 4.3 Implementar el test `test_create_cash_statement_lines_writes_foreign_fields_on_cash_receivable`
      (Slice C2.3, sigue skippeado, no relacionado a este change pero
      mismo dominio)

## 5. OpenSpec

- [x] 5.1 `openspec change validate l10n-ve-pos-payment-foreign-amount-always-computed` → válido
