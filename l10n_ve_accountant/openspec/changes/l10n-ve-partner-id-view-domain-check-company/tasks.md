# Tasks

## 1. Diagnóstico

- [x] 1.1 Confirmado el nodo xpath `//field[@name='partner_id']`
      position=replace en `l10n_ve_accountant/views/account_move.xml:97-104`
      con `domain="[('type', '!=', 'private'), ('company_id', 'in', (False, company_id))]"`
- [x] 1.2 Confirmado en core que `account.move.partner_id` tiene
      `check_company=True` (`account/models/account_move.py:426`) y que
      `res.partner._check_company_domain` es
      `check_company_domain_parent_of` (`res_partner.py:192`)
- [x] 1.3 Confirmado el mecanismo de reemplazo: `field.js:438-443`
      `dynamicInfo.domain()` usa el `domain` del nodo de la vista si existe
      y no lo concatena con el de `check_company`
- [x] 1.4 Confirmado que `('type', '!=', 'private')` no filtra nada en
      Odoo 19 (selection sin `private`)
- [x] 1.5 Confirmado que `locate_node` (`template_inheritance.py:92-93`)
      devuelve solo `nodes[0]`: el xpath reemplaza únicamente el primer
      `partner_id` del árbol (el del formulario principal), no los de las
      listas de líneas

## 2. Fix

- [x] 2.1 `l10n_ve_accountant/views/account_move.xml:100`: eliminar solo el
      atributo `domain` del nodo `partner_id` (mantener `context`,
      `options`, `invisible` y el `manually_set_rate` hermano)

## 3. Tests (TDD)

- [x] 3.1 Nuevo `l10n_ve_accountant/tests/test_partner_id_domain.py` con
      `test_form_view_partner_id_has_no_domain`,
      `test_check_company_domain_matrix_valid_unrelated_invalid` (dominio
      efectivo: nodo de la vista o `fields_get`, evaluado con `safe_eval`) y
      `test_binaural_shared_partner_satisfies_effective_domain` (condicional)
- [x] 3.2 Registrar el módulo de test en `tests/__init__.py`
- [x] 3.3 Mutación (domain viejo restaurado en la vista): falla el test 1 y
      el test 2 (solo), y los 3 tests en la suite conjunta; revert exacto
      verificado con sha256 idéntico
- [x] 3.4 Con el fix: tagged 3 tests / 0 fallos (1 omitido sin binaural);
      conjunta tagged 3 tests / 0 fallos / 0 omitidos; suite completa 298
      tests / 0 fallos

## 4. OpenSpec

- [x] 4.1 `proposal.md` + `tasks.md` + spec delta
      `specs/invoice-partner-company-domain/spec.md`
- [x] 4.2 `qc-report.md` con la salida real de los tests

## 5. Manifests

- [x] 5.1 Bump de versión en `l10n_ve_accountant/__manifest__.py`:
      `19.0.1.1.4` → `19.0.1.1.5`
