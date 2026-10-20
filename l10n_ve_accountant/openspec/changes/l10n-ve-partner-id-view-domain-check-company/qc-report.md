# QC Report — l10n-ve-partner-id-view-domain-check-company (TA84292)

## Resumen

| Item | Resultado |
|------|-----------|
| Fix | Se elimina SOLO el atributo `domain` del nodo `partner_id` en el xpath del form de factura (`views/account_move.xml`) |
| Manifest | `19.0.1.1.4` -> `19.0.1.1.5` |
| Con el fix, tagged | 3 tests, 0 fallos, 0 errores (1 omitido: el condicional, sin binaural) |
| Con el fix, conjunta tagged | 3 tests, 0 fallos, 0 omitidos (el condicional se ejecuta) |
| Con el fix, suite completa | 298 tests, 0 fallos, 0 errores |
| Mutación (domain viejo en la vista), sola | 2 de 3 fallan: test 1 y test 2 |
| Mutación, conjunta | 3 de 3 fallan |

## Causa raíz

El nodo reemplazado por `view_account_move_form_l10n_ve_accountant` declaraba
`domain="[('type', '!=', 'private'), ('company_id', 'in', (False, company_id))]"`.
En el cliente web (`field.js`, `dynamicInfo.domain()`) un `domain` en el nodo
de la vista reemplaza al del campo, que `account.move.partner_id`
(`check_company=True`) construye con `res.partner._check_company_domain`
(`check_company_domain_parent_of`). El dominio viejo excluía contactos de la
matriz y los compartidos. `type != 'private'` no filtraba nada en Odoo 19.

## Tests

`tests/test_partner_id_domain.py`, tag `l10n_ve_accountant_partner_domain`:

1. `test_form_view_partner_id_has_no_domain`: el primer nodo `partner_id` del
   form no tiene `domain` y conserva `context`, `options` e `invisible`.
2. `test_check_company_domain_matrix_valid_unrelated_invalid`: dominio efectivo
   (nodo de la vista si existe, si no `fields_get`) con `parent_of`; evaluado
   con `safe_eval` para una compañía hija, admite al contacto de la matriz y
   excluye al de una compañía ajena.
3. `test_binaural_shared_partner_satisfies_effective_domain` (condicional a
   `binaural_partner_multi_company`): contacto de una compañía ajena
   compartido con la matriz entra en el dominio efectivo; control negativo
   con el dominio de core solo; un contacto no compartido no entra.

## Evidencia

Comandos desde la raíz de `docker-multi`, base nueva por corrida (prefijo `ta84292-`):

```bash
./odoo test ta84292-review -m l10n_ve_accountant -d ta84292-r4fix --tags l10n_ve_accountant_partner_domain
# 0 failed, 0 error(s) of 3 tests (1 omitido)
./odoo test ta84292-review -m l10n_ve_accountant,binaural_partner_multi_company -d ta84292-r4joint --tags l10n_ve_accountant_partner_domain
# 0 failed, 0 error(s) of 3 tests (0 omitidos)
./odoo test ta84292-review -m l10n_ve_accountant -d ta84292-r4full
# 0 failed, 0 error(s) of 298 tests
```

Mutación (domain viejo restaurado en la vista con copia de respaldo; sha256 de
la vista idéntico antes y después, `4842c78e54a3...`):

```bash
./odoo test ta84292-review -m l10n_ve_accountant -d ta84292-r4mut --tags l10n_ve_accountant_partner_domain
# 2 failed, 0 error(s) of 3 tests
./odoo test ta84292-review -m l10n_ve_accountant,binaural_partner_multi_company -d ta84292-r4jmut --tags l10n_ve_accountant_partner_domain
# 3 failed, 0 error(s) of 3 tests
```

## Nota de integración

- Los contactos de la matriz funcionan con el `check_company_domain_parent_of`
  de core, sin binaural.
- Los contactos compartidos (`company_ids`) requieren
  `binaural_partner_multi_company` (PR integra-addons#3018); la lógica vive allí.
  El test 3 los ejercita en la suite conjunta.
- En la suite completa conjunta, dos tests de `binaural_partner_multi_company`
  fallan por sus fixtures con el stack `l10n_ve` (no tocan la vista):
  `test_t03_account_payment_shared_partner` (constraint de
  `l10n_ve_accountant/models/account_journal.py:37`: el diario se crea sin cuenta
  en sus métodos de pago) y `test_t06_native_company_id_constraint_intact`
  (`l10n_ve_contact/models/res_company.py` crea siempre un partner nuevo e ignora
  el `partner_id` recibido). Corresponden al PR #3018.
