# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducido el traceback real vía shell de Odoo.sh contra el
      registro del cliente: `CheckViolation` en
      `account_move_line_check_non_accountable_fields_null`, con la fila
      fallando siendo la sección del combo
- [x] 1.2 Confirmado que `_distribute_invoice_real_portion` no excluye
      `line_section`/`line_subsection`/`line_note` de `non_pt` ni de
      `target_lines`
- [x] 1.3 Confirmado que `_distribute_to_lines` ordena por `-abs(balance)` y
      asigna el residuo a la última línea de la lista -- una sección con
      balance=0 cae al final

## 2. Fix

- [x] 2.1 Excluir `line_section`/`line_subsection`/`line_note` en `non_pt`
      (rama con líneas `payment_term`)
- [x] 2.2 Excluir los mismos `display_type` en `target_lines` (rama `else`,
      sin líneas `payment_term`)
- [x] 2.3 Bump de manifest `19.0.1.0.13` → `19.0.1.0.14`

## 3. Test de regresión

- [x] 3.1 `test_34_line_section_never_receives_real_portion_residual`
      (`test_real_portion.py`): reproduce el error exacto sin el fix (falla
      con balance != 0 en una línea de sección) y pasa limpio con el fix
- [x] 3.2 Verificado por stash/pop del fix: sin el fix, el test falla con el
      mismo síntoma que producción; con el fix, los 34 tests de
      `test_real_portion.py` pasan

## 4. Validación en staging del cliente

- [x] 4.1 Confirmada la factura originalmente reportada tras desplegar el
      fix -- ya no tira el `CheckViolation`
- [x] 4.2 Encontradas y confirmadas otras facturas con el mismo patrón
      (secciones de combo) que estaban trabadas por la misma causa
- [x] 4.3 Verificado que ninguna línea de sección/subsección/nota quedó con
      balance, débito, crédito o cuenta contable asignados tras el posteo

## 5. OpenSpec

- [x] 5.1 `proposal.md` + spec delta
- [ ] 5.2 `openspec validate --changes`
