# Tasks

## 1. Cruce solo en Bs

- [x] 1.1 Constante `CLOSING_NOTE_LINE_KEY` y contexto en el cierre de la nota
- [x] 1.2 Helpers `_is_exchange_note`, `_holds_foreign_balance`,
      `_l10n_ve_note_foreign_values`
- [x] 1.3 Sandbox en `_prepare_reconciliation_single_partial` (un solo super)

## 2. Widget "Pagado/Revertido"

- [x] 2.1 `_get_all_reconciled_invoice_partials`: quitar filas de notas y
      agregar una por nota viva
- [x] 2.2 `_compute_payments_widget_reconciled_info`: `is_exchange_note` /
      `exchange_note_name`
- [x] 2.3 Herencia OWL + asset en `web.assets_backend`
- [x] 2.4 `i18n/es_VE.po`: "Exchange Difference Note" -> "Nota por Diferencial"
      (editado a mano; pendiente re-exportar por CLI)

## 3. Documentación y versión

- [x] 3.1 Manifest 19.0.0.0.7
- [x] 3.2 README (comportamiento y límites)
- [x] 3.3 Este change

## 4. Tests

- [x] 4.1 `tests/test_exchange_note_bs_only.py` (registrado en `tests/__init__.py`)
- [ ] 4.2 Correr la suite (tester) y revisar con `code-reviewer`

## 5. Pendiente de decisión funcional

- [ ] 5.1 Máquina fiscal (`l10n_ve_account_mf` / `l10n_ve_iot_mf`): decidir
      cómo tratar la nota en Bs (filtrar por `is_exchange_note`)
- [ ] 5.2 Cambio D separado: "una nota por pareja factura-pago"
