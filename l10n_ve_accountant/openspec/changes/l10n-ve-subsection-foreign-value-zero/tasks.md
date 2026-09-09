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

- [ ] 3.1 Test que postee un documento en moneda alterna con una línea
      `line_subsection` y verifique que queda con `foreign_balance = 0`,
      `foreign_debit = 0` y `foreign_credit = 0`
- [ ] 3.2 Test que verifique el invariante de cuadre:
      `Σ foreign_debit = Σ foreign_credit` en un asiento que contiene una
      subsección
- [ ] 3.3 Verificar por `stash`/`pop` que sin el fix el test falla con el
      descuadre, y no por otra causa

**Deuda declarada.** Este cambio se aplicó sin test propio. El fix hermano de
`l10n_ve_invoice` sí los tiene porque su síntoma es una excepción, fácil de
afirmar; acá el síntoma es un descuadre en una columna, y montar el fixture
pide un documento en moneda alterna posteado, que es justo lo que la suite de
este módulo no puede armar sobre base clonada. Queda anotado en vez de
declararlo cubierto.

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
