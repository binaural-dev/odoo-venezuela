# Tasks

## 1. Diagnóstico

- [x] 1.1 Confirmado con `git log -L` sobre `onchange_partner_id()` que el
      método nunca cubrió ISLR/municipal, solo IVA, desde su introducción
      en 17.0
- [x] 1.2 Confirmado que la vista ISLR (`view_retention_islr_form_...`)
      dispara `onchange_partner_id(type, partner_id)` y tiene
      `retention_line_ids` editable en la misma pantalla, habilitando el
      escenario del ticket (agregar líneas, cambiar partner, líneas
      quedan huérfanas)
- [x] 1.3 Confirmado que no existía ninguna validación de servidor
      (`@api.constrains` o en `action_post()`) comparando
      `retention_line_ids.move_id.partner_id` contra `partner_id`

## 2. Fix

- [x] 2.1 `onchange_partner_id()` reescrito a un solo loop; ISLR/municipal
      ahora llaman `clear_retention()` al cambiar el partner
- [x] 2.2 Nueva constraint `_check_lines_match_partner()`, excluyendo
      `is_third_party_retention`
- [x] 2.3 Limpieza incidental: 6 `states={"draft": [...]}` muertos
      retirados de `account.retention` (ya no soportados por el ORM)

## 3. Verificación

- [x] 3.1 `test_islr_lines_cleared_when_partner_changes`: cambiar partner
      en el formulario limpia las líneas (simulado con `Form`, no
      `.create()` directo, para reproducir la semántica real de
      NewId/onchange del cliente web)
- [x] 3.2 `test_mismatched_partner_lines_blocked_on_save`: crear una
      retención con línea de otro partner lanza `ValidationError`
- [x] 3.3 Confirmado que ambos tests fallan sobre el código anterior (la
      línea sobrevive / no hay excepción) y pasan con el fix
- [x] 3.4 Suite completa del módulo corrida en aislado antes y después del
      refactor de `onchange_partner_id`: mismo resultado, sin fallos
      (incluye el flujo de retenciones a terceros, no afectado por la
      nueva constraint)

## 4. OpenSpec

- [x] 4.1 `proposal.md` + spec delta (`ADDED` - capability nueva)
- [ ] 4.2 `openspec validate --changes` (no ejecutado: CLI `openspec` no
      disponible en este entorno)

## 5. Proceso (pendiente, no técnico)

- [x] 5.1 Commit `[FIX] l10n_ve_payment_extension: retencion ISLR permitia
      confirmar con lineas de otro partner` en la rama
      `maint-19.0-ti-15341-15076-15337-fix-retention-validations`
- [ ] 5.2 Push a `origin` (pendiente de confirmación explícita)
