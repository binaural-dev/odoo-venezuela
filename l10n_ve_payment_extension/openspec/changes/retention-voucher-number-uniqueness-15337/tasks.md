# Tasks

## 1. Diagnóstico

- [x] 1.1 Confirmado en el ORM de Odoo (`orm/models.py:copy_data`) que
      todo campo sin `copy=False` se copia tal cual al duplicar,
      incluyendo one2many de forma recursiva
- [x] 1.2 Confirmado que `account.retention` no tenía `copy=False` en
      `number`, `state`, `correlative`, `retention_line_ids` ni
      `payment_ids`
- [x] 1.3 Confirmado que `create()` ya llama a `_set_sequence()`
      (asigna número solo si `not r.number`) - la causa raíz exacta es
      que duplicar dejaba `number` ya poblado, por lo que ese guard nunca
      se disparaba para el duplicado
- [x] 1.4 Confirmado que no existía ninguna constraint de unicidad sobre
      `number`

## 2. Fix

- [x] 2.1 `copy=False` en `number`, `state`, `correlative`,
      `retention_line_ids`, `payment_ids`
- [x] 2.2 Nueva constraint `_check_number_unique()`, alcance
      `(company_id, type_retention)`

## 3. Verificación

- [x] 3.1 Duplicar una retención "Emitida" con líneas: el duplicado queda
      en borrador, sin número igual al original (numero nuevo asignado
      por `_set_sequence()`), sin líneas ni pagos
- [x] 3.2 Crear dos retenciones con el mismo `number` y mismo
      `type_retention` lanza `ValidationError`
- [x] 3.3 El mismo `number` en `type_retention` distintos no bloquea
      (secuencias independientes)
- [x] 3.4 Suite completa del módulo corrida en aislado: 1 fallo
      encontrado (`test_cross_retention_islr_concept_base_exceeded_blocks_on_emitted`,
      descuido preexistente con número hardcodeado repetido) y corregido
      en `test_retention_ti14548_rules.py`
- [x] 3.5 Suite completa recorrida tras el ajuste: 432 tests, sin fallos

## 4. OpenSpec

- [x] 4.1 `proposal.md` + spec delta (`ADDED` - capability nueva)
- [ ] 4.2 `openspec validate --changes` (no ejecutado: CLI `openspec` no
      disponible en este entorno)

## 5. Proceso (pendiente, no técnico)

- [x] 5.1 Commit `[FIX] l10n_ve_payment_extension: comprobante duplicado
      permitido en retenciones IVA/ISLR` en la rama
      `maint-19.0-ti-15341-15076-15337-fix-retention-validations`
- [ ] 5.2 Push a `origin` (pendiente de confirmación explícita)
