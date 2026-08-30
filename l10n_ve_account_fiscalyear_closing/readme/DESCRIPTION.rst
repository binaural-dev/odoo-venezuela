El módulo "Venezuela - Cierre Fiscal" adapta el asistente genérico de cierre
de año fiscal (`account_fiscal_year_closing`) a las necesidades contables de
Venezuela: cierres bimoneda (Bolívares y la moneda alterna configurada),
carga automática de los mapeos de las cuentas de resultado y validaciones
propias del proceso de cierre local.

Depende de `account_fiscal_year_closing`, `l10n_ve_accountant`,
`l10n_ve_contact` y `l10n_ve_rate`.

Funcionalidad propia de este módulo:

* Autocompleta los mapeos de cuentas de ingreso y gasto hacia la cuenta de
  "Resultados del ejercicio actual" (equity_unaffected) con solo activar el
  interruptor "Cargar Cuentas" en la configuración del cierre o de su
  plantilla.
* Genera un asiento de cierre por cada cuenta con saldo en el período,
  tomando tanto el saldo en Bolívares como el saldo en la moneda alterna
  (bimoneda) directamente de los asientos de origen, sin inventar ninguna
  tasa de cambio.
* No permite calcular un cierre si la compañía no tiene configurada una
  cuenta de tipo "Resultados del ejercicio actual", ni si existen asientos
  en borrador dentro del período (cuando esa verificación está activa).

Heredado de `account_fiscal_year_closing` (el asistente genérico del que
depende este módulo, no lógica propia de la localización venezolana):

* Respeta la fecha de bloqueo contable de la compañía: si la fecha de un
  asiento de cierre cae dentro de un período bloqueado, el cálculo se
  detiene con un mensaje de error en lugar de mover la fecha en silencio.
  Este módulo solo invoca esa validación desde su propio `calculate()`
  (que reemplaza por completo el del módulo base).
* No permite crear cierres fiscales duplicados o solapados para una misma
  compañía: pueden coexistir varios cierres en el mismo año (por ejemplo,
  semestrales) siempre que sus rangos de fechas no se crucen.
* Al cancelar o recalcular un cierre, los asientos que ya fueron
  contabilizados nunca se eliminan: se desconcilian y se cancelan,
  quedando disponibles para auditoría. Solo se eliminan los asientos que
  nunca llegaron a contabilizarse.
