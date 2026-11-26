## Why

El Estado de Situación Financiera en $ de MAXCAM no cuadra (−734.161,13 USD al 12/11/2026) y el de Bs sí. El reporte suma `foreign_balance` y hay asientos publicados que cuadran en Bs pero no en $, porque el core solo valida el cuadre en la moneda de la compañía. Una parte son pagos bancarios en Bs con contrapartida en USD (diarios `O-`, p. ej. `OB002/2026/1425`); producción tiene unos 700 y se siguen creando.

Causas:

1. **La línea del banco no seguía a su contrapartida.** La línea de extracto en Bs nace con la cuenta puente (Bs) como contrapartida y la línea del banco toma su monto en $ a la tasa del día (1.700.000 / 886,2 = 1.918,30). Al conciliar, la contrapartida pasa a USD (1.700 USD por 1.700.000 Bs). `_get_non_invoice_foreign_value` ya toma de ella el monto con signo contrario (1.700), pero `_compute_foreign_debit_credit` solo dependía de campos de su propia línea y nada la recalculaba: el asiento quedaba en −218,30 en $.
2. **El diálogo "Editar línea" del widget de conciliación guardaba el par `balance` / `amount_currency` sin coherencia con la tasa.** El formulario deja editar los dos a la vez y `edit_reconcile_line` los guarda tal cual: USD 1.700 con 1.700.000 Bs (tasa implícita 1000) cuando la tasa de la fecha era 924,3534. El core, en un asiento manual, recalcula el balance desde el monto en moneda (`_inverse_amount_currency`). Conciliando sin editar la línea el widget ya quedaba coherente; el desacople solo aparecía al forzar el balance a mano.
3. **La línea del extracto con solo el monto en moneda extranjera quedaba en 0 Bs.** En el core `amount` (moneda del diario) manda y `amount_currency` solo se calcula desde él, nunca al revés. En un diario sin moneda USD, una línea creada con USD 10,82 y `amount` en 0 genera un asiento de 0 Bs en ambas líneas; al conciliar el pago (10.000 Bs) contra ella, el core manda los 10.000 Bs al diferencial cambiario (`BNK3/2026/0002` en staging).

## What Changes

- `account.move.line._compute_foreign_debit_credit` depende también de `move_id.line_ids.amount_currency` y `move_id.line_ids.currency_id`: al cambiar la contrapartida, la línea del banco se recalcula con la regla existente.
- `account.bank.statement.line.edit_reconcile_line` (de `account_accountant`) se sobrescribe: el último campo editado manda. Si cambia el monto en moneda, el balance sale de monto / tasa de la fecha del asiento; si cambia solo el balance o la moneda, el monto en moneda sale de balance × tasa. No se toca si la moneda es la de la compañía ni si la línea ya está conciliada (el monto parcial sigue la tasa del documento). La diferencia contra el extracto queda en la cuenta puente.
- `account.bank.statement.line.create`: si llega `amount_currency` con moneda extranjera distinta de la del diario y `amount` está en 0 o vacío, `amount` sale del monto en moneda extranjera a la tasa de la fecha del extracto. Un `amount` explícito se respeta.
- `account_accountant` se declara en las dependencias del manifest (ya llegaba por `account_reports`).
- Versión 19.0.1.0.51. Pruebas: `tests/test_foreign_unbalanced_16410.py` (12 casos).

## Impact

- **Specs afectadas**: `l10n_ve_accountant` (débito y crédito alterno por apunte contable; coherencia de balance y monto en moneda al editar una línea del widget; monto en Bs de la línea de extracto creada solo en moneda extranjera).
- **Código**: `models/account_move_line.py`, `models/account_bank_statement_line.py`, `__manifest__.py`. Sin migración ni textos nuevos.
- **Qué ve el usuario**: el asiento de un extracto en Bs conciliado contra USD cuadra en $; al forzar el balance en "Editar línea" el monto en moneda se ajusta a la tasa de la fecha (si se cambia el monto en moneda, el balance se ajusta y la diferencia pasa a la cuenta puente).
- **Lo que no cambia**: la conciliación sin editar la línea, las líneas en moneda de la compañía y las líneas ya conciliadas.
- **Datos existentes**: no se corrigen por migración; los asientos ya publicados se recalculan con un script aparte (`SCRIPT_CORRECCION_16410.py`, `DRY_RUN` por defecto). Los saldos iniciales (`MB0xx`, `MISCM`) son datos del cliente y no se tocan.
- **Fuera de alcance**: aviso en los reportes en $ y lista de asientos descuadrados (`binaural_account_reports`), y una línea automática contra el diferencial cambiario o una tolerancia (decisión de producto junto con la validación al publicar del #16200).
