# Tasks

## 1. Diagnóstico

- [x] 1.1 Confirmado en `pos2` que las dos facturas son idénticas línea por
      línea y que solo difiere el importe alterno del `payment_term`
- [x] 1.2 El descuadre de `INV/2026/0204` (42,77 débito vs 42,56 crédito) es
      exactamente el crédito de sus tres líneas COGS
- [x] 1.3 Confirmado en core que `stock_account._post()` crea los COGS **antes**
      de `super()._post()`, con el asiento aún en `draft`
- [x] 1.4 Origen de la fórmula bruta: commit `8a048a82b` (2026-06-15, SaulOrte),
      presente en `origin/19.0`
- [x] 1.5 Explicado por qué la rama daba 42,35 antes del merge: su bloque de
      residuo vivía en un compute `store=True` que no depende de las líneas
      hermanas, así que corría antes de que existieran los COGS

## 2. Merge de `origin/19.0` (commit `124e9fe02`, previo al fix)

La rama no contenía `8a048a82b`, así que arrastraba su propio bloque de residuo
dentro de `_compute_foreign_debit_credit`. Se mergeó `origin/19.0` para no
mantener dos mecanismos en paralelo y arreglar sobre el que ya existe.

- [x] 2.1 Divergencia medida: 246 commits entrantes, 119 propios, base
      `1d3f86b71` (2026-06-07)
- [x] 2.2 Simulado con `git merge-tree` antes de ejecutarlo: 4 conflictos
- [x] 2.3 Verificado en el árbol simulado que no quedan dos mecanismos: el
      bloque "Ajuste de residuo" de `account_move_line.py` desaparece y solo
      sobrevive `_distribute_foreign_pt_residual`
- [x] 2.4 `l10n_ve_accountant/__manifest__.py` → versión de 19.0 (19.0.1.0.8)
- [x] 2.5 `l10n_ve_invoice/__manifest__.py` → versión de 19.0 (19.0.1.0.6)
- [x] 2.6 **Decisión de criterio.** `l10n_ve_invoice/models/account_move.py`:
      conservado el `_onchange_move_type` con `fields.Date.context_today` de la
      rama. `origin/19.0` no lo tiene y su `default` sigue siendo
      `fields.Date.today`, así que tomar el lado de 19.0 habría reintroducido
      el bug de zona horaria documentado en
      `l10n-ve-invoice-date-display-timezone-fix`
- [x] 2.7 **Decisión de criterio.** `l10n_ve_igtf/models/account_move.py`,
      `compute_bi_igtf`: cada lado había arreglado algo distinto y se
      combinaron los dos. De 19.0 (`4bae51955`) la inicialización a cero de los
      cuatro campos computados y la condición sobre `amount_residual`, que es
      lo que declara el `@api.depends`. De la rama, `rec.company_id` en lugar
      de `self.company_id`, que dentro de un `for rec in self` es incorrecto en
      multi-registro
- [x] 2.8 `git reset --hard 6550fe04c` revierte el merge entero

## 3. Fix

- [x] 3.1 Contrapartida en neto en la rama de moneda de compañía / alterna
- [x] 3.2 Guarda de neto negativo con vuelta al bruto
- [x] 3.3 Commit propio, separado del merge (`git reset --hard 124e9fe02` lo
      revierte sin deshacer el merge)

## 4. Verificación de flujos

- [x] 4.1 Único punto de llamada: `_sync_dynamic_lines`. No hay otras entradas
- [x] 4.2 Descartados por las guardas de la función: pagos, IGTF, anticipos,
      retenciones, cierres de PdV, extractos, nómina, costes en destino (todos
      `entry`), cualquier asiento publicado, tercera moneda, y compañías sin
      moneda alterna
- [x] 4.3 Identificados los únicos tipos de línea que caen del mismo lado que
      el término de pago: `cogs` (165 facturas + 13 notas), `product` de precio
      negativo (8 + 4) y sus `tax` derivados (2 + 4)
- [x] 4.4 Confirmado que el único flujo cuyo comportamiento cambia es el de
      facturación con valoración de inventario en tiempo real
- [x] 4.5 Revisados los 22 tests de `test_real_portion.py`: del 07 al 22 son
      asientos manuales que la función descarta; del 01 al 06 son facturas
      (USD, EUR, VEF, uno y tres plazos) y ninguno monta valoración en tiempo
      real, así que el neto coincide con el bruto y pasan sin cambios
- [x] 4.6 Simulación sobre los 207 documentos posteados de `pos2` que entran
      por esta rama: 30 cuadrados → 0 cambian; 177 descuadrados → 176 corregidos
- [x] 4.7 Probado en navegador por el usuario: sesión `Binaural C.A/00129`,
      orden `Binaural C.A - 000032`, factura `INV/2026/0208` (id 1066)
- [x] 4.8 La factura cuadra: 42,56 al debe contra 42,56 al haber en la columna
      alterna, con las tres parejas de COGS presentes
- [x] 4.9 Confirmado que corrió el código nuevo y no el compute antiguo: la
      línea de término de pago quedó con `not_foreign_recalculate = t`, que
      solo escribe `_distribute_foreign_pt_residual` (en `INV/2026/0205`, de
      antes del merge, ese flag está en NULL)
- [x] 4.10 Los 13 asientos del flujo completo cuadran en la columna alterna:
      factura, venta POSS, IGTF, cierre de sesión, pago en Bs y pago en divisa
      con IGTF (`CSH2/2026/0062`)

## 5. Pendiente, decidido fuera de este cambio

- [ ] 5.1 Corregir el aserto `_assert_pt_vs_other_foreign`
      (`test_real_portion.py:192`), que codifica la invariante bruta y fallará
      en cuanto exista un test con COGS
- [~] 5.2 Data-fix: descartado en `pos2`, que es base de pruebas y se deja como
      está. Queda como consideración para quien despliegue: los documentos ya
      publicados no se corrigen solos, porque la función solo actúa sobre
      borradores y la línea de término de pago queda congelada con
      `not_foreign_recalculate = t`
- [ ] 5.3 Líneas de precio negativo sin importe alterno en el PdV
      (201.855,30 Bs); ya bloqueadas para órdenes nuevas
- [ ] 5.4 Redondeo acumulado de `foreign_subtotal` en facturas grandes
- [ ] 5.5 Cobrable que no coincide con el pago (179 de 190 facturas); medido
      que `foreign = |balance| × tasa` lo dejaría todo dentro de 2 céntimos
- [ ] 5.6 Auditar la porción real que trajo el merge

## 6. OpenSpec

- [x] 6.1 `proposal.md` + spec delta
- [x] 6.2 `openspec validate --changes`
