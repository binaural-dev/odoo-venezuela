# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducir el descuadre en la sesión Binaural C.A/00043 (SQL
      directo sobre `pos` / `proj_db`): líneas 1018 y 1019 del asiento
      288 en 0.00, comprobado contra sus líneas hermanas en los asientos
      de extracto separados y contra el descuadre de la columna foreign
      del asiento (40.75 vs 83.67)
- [x] 1.2 Ubicar la causa raíz en `set_foreign_amount_in_line` (todo el
      cuerpo anidado bajo `if other_lines:`, vacío para las líneas del
      asiento de cierre)

## 2. Implementación

- [x] 2.1 `models/pos_session.py::set_foreign_amount_in_line`: separar el
      match por monto de la sincronización de la línea contraparte;
      escribir siempre en `line` cuando hay match
- [x] 2.2 Verificar sintaxis (`ast.parse`) — sin acceso a Odoo cargado
      para correr el test suite completo en este pase

## 3. Validación

- [x] 3.1 Revisión independiente con Opus (agente separado, sin el
      diagnóstico previo como input ciego): confirma causa raíz, confirma
      que no rompe el camino que ya funcionaba (líneas con contraparte),
      señala hueco de test (C2.3 skip) y caso borde de colisión de monto
      entre métodos combine
- [ ] 3.2 Correr la suite de tests de `l10n_ve_pos` (`test_pos_session_*`)
      en el contenedor `proj` — pendiente, no ejecutado en este pase

## 4. Pendiente (fuera de alcance de este change, con seguimiento)

- [ ] 4.1 Implementar `test_create_cash_statement_lines_writes_foreign_fields_on_cash_receivable`
      (actualmente `@unittest.skip`, Slice C2.3) como cobertura de
      regresión de este fix
- [ ] 4.2 Data-fix de los asientos ya generados con el bug en la sesión
      00043 (líneas 1018, 1019, 1020 del asiento 288) — recalcular
      `foreign_debit`/`foreign_credit` a partir de la tasa del asiento y
      marcar `not_foreign_recalculate`
- [ ] 4.3 Auditar si otras sesiones cerradas antes de este fix tienen el
      mismo patrón (método de pago efectivo "combine" con
      `is_foreign_currency = True`)

## 5. OpenSpec

- [x] 5.1 `openspec change validate l10n-ve-pos-session-close-cash-foreign-amount-fix` → válido
