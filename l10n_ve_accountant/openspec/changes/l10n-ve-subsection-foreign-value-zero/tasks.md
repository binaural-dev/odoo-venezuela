# Tasks

## 1. Diagnóstico

- [x] 1.1 Identificado `line_subsection` como `display_type` nuevo de Odoo 19
      en la familia de líneas de maquetado, mientras auditábamos el bloqueo
      de facturación de `l10n_ve_invoice` (tarea 82254, cotización S11508)
- [x] 1.2 Auditadas las tuplas de `display_type` del módulo buscando la misma
      omisión: aparece en la rama 2 de `_get_foreign_value()`
- [x] 1.3 Confirmado que sin `line_subsection` en esa tupla la línea cae por
      las ramas siguientes y puede recibir un `foreign_balance` distinto de
      cero
- [x] 1.4 Confirmado que el defecto es SILENCIOSO: no hay guard que lo
      detenga, el asiento postea y queda descuadrado en la columna alterna

## 2. Fix

- [x] 2.1 Agregar `"line_subsection"` a la tupla de la rama 2 de
      `_get_foreign_value()`
- [x] 2.2 Comentario en el código explicando de dónde viene el
      `display_type` y qué pasaba sin él
- [x] 2.3 Bump de manifest `19.0.1.0.15` → `19.0.1.0.16`

## 3. Test de regresión

- [x] 3.1 `test_01b_subsection_gets_no_foreign_amount_and_entry_squares`
      (`tests/test_real_portion.py`): postea una factura en USD con sección,
      subsección, producto con IVA y nota, y verifica que las tres líneas de
      maquetado quedan con `foreign_balance`, `foreign_debit` y
      `foreign_credit` en 0
- [x] 3.2 El mismo test cierra con `_assert_balances()` y
      `_assert_foreign_squares()`, el helper que ya existía en el archivo
      (`:185`) y que es exactamente el invariante que pedía esta tarea
- [x] 3.3 Verificado revirtiendo la tupla de `_get_foreign_value()` a
      `("line_section", "line_note")` y reejecutando el tag. **Resultado que
      corrige el supuesto de esta tarea:** sin el fix falla SOLO
      `test_01c`; `test_01b` sigue verde
- [x] 3.4 `test_01c_subsection_exclusion_precedes_manual_adjustments`: es el
      test que SÍ discrimina el fix. Pone `foreign_debit_adjustment` en la
      subsección y verifica que igual queda en 0, o sea que la exclusión se
      evalúa antes de las ramas de ajuste manual

**Deuda cancelada, y el motivo declarado era falso.** La versión previa de
este documento decía que el fixture "pide un documento en moneda alterna
posteado, que es justo lo que la suite de este módulo no puede armar sobre
base clonada". Un code review lo desmintió con la evidencia a la vista: el
`setUp` de `tests/test_real_portion.py` (`:14-50`) ya escribe
`company.foreign_currency_id = USD` y crea las tasas, `test_01` (`:228`) ya
postea una factura en esa moneda, y `_assert_foreign_squares()` (`:185`) ya
es la afirmación pedida. Eran 33 tests haciendo lo que este documento
declaraba imposible. El revisor tenía razón; los tests se escribieron.

**Hallazgo de alcance, medido.** El punto 3.3 dejó a la vista que el
síntoma NO es alcanzable por las ramas de conversión: en una factura, core 19
impide `amount_currency != 0` en una línea de maquetado por CHECK constraint,
así que la subsección nunca recibe importe por esa vía. Las rutas realmente
alcanzables son los ajustes manuales (ramas 3 y 4) y
`_get_non_invoice_foreign_value()` (rama 7, asientos que no son factura). Eso
acota el `Impact` de `proposal.md`, que sobredimensionaba el alcance.

Comando exacto:

```
odoo -d <db> --without-demo=all -i l10n_ve_accountant --test-enable \
     --test-tags l10n_ve_accountant_real_portion --stop-after-init
```

Corrido en base fresca: 36 tests, 0 fallos.

## 4. Corrección de datos

- [ ] 4.1 Detectar asientos ya posteados afectados. A diferencia del cambio
      hermano, acá no hubo guard que impidiera persistir:

      ```sql
      SELECT aml.move_id, am.name,
             SUM(aml.foreign_debit) AS fdeb,
             SUM(aml.foreign_credit) AS fcred
        FROM account_move_line aml
        JOIN account_move am ON am.id = aml.move_id
       WHERE am.state = 'posted'
         AND aml.move_id IN (
               SELECT move_id FROM account_move_line
                WHERE display_type = 'line_subsection'
             )
       GROUP BY aml.move_id, am.name
      HAVING SUM(aml.foreign_debit) <> SUM(aml.foreign_credit);
      ```

- [ ] 4.2 Para los que aparezcan, verificar si la subsección tiene
      `foreign_balance`, `foreign_debit` o `foreign_credit` distinto de cero
- [ ] 4.3 Decidir con el consultor si se corrigen a mano o se re-sincronizan.
      NO asumir que la lista está vacía sin correr la consulta: `line_subsection`
      está disponible en la UI de Odoo 19, así que cualquier usuario pudo
      haber creado uno

## 5. OpenSpec

- [x] 5.1 `proposal.md` + spec delta
- [x] 5.2 `openspec validate --changes` -> 5 passed, 0 failed
