# l10n_ve_rate: riesgo de negocio en la línea NO homologada, sin corrección automática

============================================================================
LÍNEA NO HOMOLOGADA (rama 17.0 de integra-addons, binaural_rate)
============================================================================

Del inventario campo por campo (ver `INVENTARIO_MODULOS_NO_HOMOLOGADOS.md`,
sección `binaural_rate` + `binaural_currency_rate_live`):

El rename `res_company.currency_foreign_id` → `foreign_currency_id` que
`l10n_ve_rate/migrations/19.0.1.3.0/pre-migrate.py` ya hace es 100%
reutilizable para esta línea también -- mismo nombre de columna vieja,
mismo guard de idempotencia. **No requiere ningún cambio y no se toca en
esta carpeta.**

Lo que **no se puede resolver con un script de datos** es que
`res.currency.rate.compute_rate()` tiene la condición y el mapeo de qué
campo se expone como `foreign_rate` (cuando la divisa extranjera es USD)
**invertidos** entre `binaural_rate` v17 y `l10n_ve_rate` v19:

- `binaural_rate` v17 (`models/res_currency_rate.py`, línea ~9-67): cuando
  `foreign_currency_id == USD`, `foreign_rate` toma el valor de
  `inverse_company_rate`.
- `l10n_ve_rate` v19 (`models/res_currency_rate.py`, línea ~11-61): en el
  mismo caso, `foreign_rate` toma el valor de `company_rate` (no
  `inverse_company_rate`).

Esto **no es un rename de columna** -- es lógica de negocio distinta bajo
el mismo nombre de método. Si un cliente de la línea `binaural_rate`
termina usando el modelo `l10n_ve_rate` de v19 tal cual (sin decidir
explícitamente qué fórmula es la correcta para su caso), el cálculo de
tasa cambiaría de comportamiento **silenciosamente** -- ningún script de
migración de datos puede detectar o corregir esto, porque no hay una
columna "incorrecta" que respaldar: es la fórmula la que difiere.

Adicionalmente, `binaural_currency_rate_live` (cron de actualización BCV,
campo `res_company.currency_provider` con opción "bcv", y
`can_update_habil_days`) **no tiene ningún equivalente en `l10n_ve_rate`**
-- si no se decide un destino, ese cron y su configuración se pierden por
completo al migrar.

## Decisión pendiente (no tomada en este documento)

Antes de escribir cualquier script de migración de datos para
`binaural_rate`/`binaural_currency_rate_live`, alguien con conocimiento de
negocio debe confirmar:

1. ¿Cuál de las dos fórmulas de `compute_rate()` es la correcta para los
   clientes de la línea no homologada? (¿o ambas eran correctas para sus
   respectivos contextos y no deben unificarse?)
2. ¿El cron BCV (`binaural_currency_rate_live`) debe portarse a un módulo
   propio en v19, o se reemplaza por otro mecanismo ya existente en la
   línea homologada no cubierto por este inventario?

Hasta que eso se decida, **no se debe instalar `l10n_ve_rate` sobre una
base que viene de `binaural_rate` asumiendo equivalencia de
`compute_rate()`** -- solo el rename de columna es seguro de reutilizar
tal cual.
