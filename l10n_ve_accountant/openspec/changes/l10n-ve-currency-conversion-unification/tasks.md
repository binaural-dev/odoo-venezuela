# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducido el desfase reportado (300 USD → 300,57) y trazado hasta
      la convivencia de dos vías de conversión: multiplicar por
      `foreign_inverse_rate` vs. `_convert()`
- [x] 1.2 Identificada la causa raíz: la migración v17 (base USD) → v19
      (base VEF) intercambió el significado de `foreign_rate` y
      `foreign_inverse_rate` en `compute_rate`
- [x] 1.3 Inventariados los 8 sitios productivos que multiplican por una tasa
      en los tres repos, clasificados por dirección correcta / invertida /
      rama muerta
- [x] 1.4 Verificado en instancia que `compute_all` sigue vigente en el core
      de v19 (42 llamadas, sin marca de deprecación) y que el core hace la
      misma separación entre motor nuevo y `compute_all`
- [x] 1.5 Medido el impacto del redondeo: ida y vuelta exacto (error 0) con
      `round=False` + `float_round`; y 13,79% de desvío con impuesto incluido
      en precio si no se usa `compute_all`
- [x] 1.6 Confirmado que `tax_totals` ya trae el monto alterno correcto en una
      tercera moneda (PO en EUR: 110,01 por ambas vías)

## 2. `l10n_ve_accountant`

- [x] 2.1 `_get_foreign_rate_date()` como única fuente de fecha de la línea
- [x] 2.2 `_compute_foreign_price`: `_convert(round=False)` + `float_round` a
      "Foreign Product Price", guard de moneda alterna ausente
- [x] 2.3 `_compute_price_unit_ves`: `_convert()` en lugar de dividir entre
      `currency_id.rate` (elimina además un `ZeroDivisionError` latente)
- [x] 2.4 `_get_non_invoice_foreign_value`: usa el helper de fecha
- [x] 2.5 `@api.depends` completados con `currency_id`, `move_id.invoice_date`
      y `move_id.date` en los tres computes afectados
- [x] 2.6 `_compute_foreign_taxable_income`: acceso con `.get(..., 0)`
- [x] 2.7 `_compute_foreign_total_billed`: se lee de `tax_totals`, sin la rama
      que reconvertía en tercera moneda
- [x] 2.8 `_compute_foreign_subtotal` ya usaba `compute_all` desde v16: sin
      cambios
- [x] 2.9 (TI-15055, posterior) `_prepare_product_foreign_base_line_for_taxes_computation`
      quedó fuera del inventario original: usaba `move.foreign_rate` (campo
      informativo, redondeado a "Tasa" = 6 decimales) como `rate` del motor
      de impuestos, en vez del valor exacto que produjo `_convert()` para esa
      línea. Corregido derivándolo de `foreign_price / price_unit` de la
      propia línea -- mismo patrón que la rama no-factura
      (`amount_currency / balance`)
- [x] 2.10 (TI-15055) `_sync_tax_lines`/`_round_mode` no resincronizaba la
      línea de impuesto cuando cambiaba `invoice_date`/`date` sin que
      cambiara nada más del cálculo en moneda de la compañía (precio,
      cantidad, `tax_ids`). Se agregó `invoice_date`/`date` al snapshot de
      `moves_values_before` y un disparador en `_round_mode` que fuerza la
      resincronización (`round_from_tax_lines=True`) cuando cualquiera de
      los dos cambia -- son las mismas fechas que
      `_get_foreign_rate_date()` usa como fuente de la tasa, consistente
      con 2.1. Se corrigió además `get_value()`, que pedía el campo
      siempre a `account.move.line` en vez de al modelo real del record
      (reventaba con `KeyError` al trackear un campo que solo existe en
      `account.move`)
- [x] 2.11 (TI-15055, code review de 2.9/2.10) Con 2.9 resuelto,
      `move_id.foreign_rate` en el `@api.depends` de
      `_compute_foreign_price` (`account_move_line.py`) quedó como
      disparador muerto: el compute nunca lee `foreign_rate`, convierte
      por fecha con `_get_foreign_rate_date()`. Eliminado del `depends`.
      `_prepare_epd_foreign_base_line_for_taxes_computation` y
      `_prepare_cash_rounding_foreign_base_line_for_taxes_computation`
      (`account_move.py`) seguían con `rate = self.foreign_rate` sin
      tocar -- mismo requirement, mismo argumento que 2.9. Corregidas
      para derivar `rate` de la conversión ya hecha en esa línea
      (`converted / amount_currency`), completando el inventario de
      sitios que arman `rate` para la rama foránea del motor de
      impuestos
- [x] 2.12 (TI-15055) Cobertura agregada: el test original de 2.10 solo
      cubría compra (mira `date`) escribiendo `invoice_date`+`date`
      juntas. Se agregó `test_invoice_tax_line_foreign_recompute_on_invoice_date_only`
      -- factura de VENTA escribiendo solo `invoice_date`, el escenario
      real del ticket y de la UI
- [x] 2.13 (TI-15055) No aplica: los asientos `move_type='entry'` no
      llevan impuestos (`tax_repartition_line_id`), así que nunca tienen
      línea `display_type='tax'` -- el camino que agrega 2.10
      (`get_tax_lines`, `tax_results['tax_lines_to_add'/'to_update']`)
      no tiene nada que resincronizar en ese `move_type`. El riesgo que
      señaló el reviewer no era real
- [x] 2.14 (hallazgo posterior, sin ticket) `_apply_vef_first` (rama
      `round_globally`, entonces resuelta con un helper `_vef_base_for_tax`
      luego fusionado en `_grouped_tax_sums` por la tarea 2.16 -- ver ahí)
      sumaba la base VEF de TODAS las líneas de producto que comparten un
      mismo impuesto y redondeaban una sola vez, sin importar el valor de
      `company.tax_calculation_rounding_method`. Con `round_per_line` (el
      modo que exige la máquina fiscal venezolana: redondear el impuesto de
      cada línea y luego sumar), el resultado divergía en céntimos del
      método legal, y `amount_currency` (nativo) quedaba desalineado de
      `foreign_debit`/`foreign_credit` (columna alterna, que ya redondeaba
      por línea vía `_prepare_product_foreign_base_line_for_taxes_computation`).
      Reproducido con datos reales (tasa 803,34; 2 líneas de 11,16 USD;
      IVA 16%: esperado 2.868,88 Bs, el código daba 2.868,89 Bs en ambos
      modos). Corregido agregando `_per_line_tax_sums`: cuando el modo es
      `round_per_line`, calcula y redondea el impuesto de cada línea de
      producto (en VEF y en moneda de documento) antes de sumar, en vez de
      sumar bases primero. Tests `test_28`/`test_29`/`test_30` en
      `test_multi_currency_rounding.py`
- [x] 2.15 (code review de 2.14) Tres hallazgos sobre el fix anterior:
      (1) el widget de totales/PDF (`account.tax._get_tax_totals_summary`)
      se calcula de forma independiente desde `base_lines` vía el motor
      del core, así que seguía mostrando el monto agrupado-y-redondeado-
      una-vez aunque la línea de impuesto real ya tuviera el monto
      correcto por línea -- factura y asiento contable discrepaban en el
      mismo caso que el fix quería cerrar. Corregido agregando
      `AccountTax._fix_tax_amount_for_round_per_line`, que sobrescribe
      `tax_amount`/`tax_amount_currency` (y sus subtotales/grupos de
      impuesto) desde las líneas de impuesto reales cuando el modo es
      `round_per_line`. (2) `_per_line_tax_sums` usaba
      `abs(record.price_subtotal)` para el lado en moneda de documento,
      con un signo global aplicado después -- con líneas de signo mixto
      bajo el mismo impuesto (descuento global, ajuste negativo) el
      `abs()` sumaba lo que debía restar. Corregido sumando
      `to_update['amount_currency']` (firmado, ya fresco) de cada línea,
      igual que el lado VEF. (3) El `_get_tax_totals_summary` original
      quedó demasiado largo con este fix inline; extraído a
      `_fix_base_amount_for_multi_currency` y
      `_fix_tax_amount_for_round_per_line`, dejando el método principal
      en ~10 líneas. Tests: `test_28` ahora fija `round_per_line`
      explícitamente (antes corría por la rama vieja sin querer, el
      default de la compañía es `round_globally`); `test_30` agrega el
      assert de `inv.amount_tax` contra el widget; `test_31` nuevo cubre
      líneas de signo mixto
- [x] 2.16 (seguimiento de 2.14/2.15) Optimización y cobertura adicional,
      verificadas exhaustivamente con `tax.compute_all()` de Odoo como
      oráculo independiente (no fórmulas propias) sobre el código real
      corrido con `--addons-path` explícito (ver nota de infraestructura
      en memoria de sesión sobre `vertical1` vs `vertical3`):
      - **Performance**: `_vef_base_for_tax`/`_per_line_tax_sums`
        recorrían todas las `base_lines` por cada repartition line
        (O(n × impuestos)). Precalculado una vez en `lines_by_tax_id`
        (índice `tax_id → líneas`), quedando O(n) para la indexación más
        O(k) por consulta (k = líneas que usan ese impuesto).
        (Seguimiento en 2.17: `_vef_base_for_tax` quedó código muerto tras
        la tarea de `include_base_amount` de abajo, y se eliminó.)
      - **`include_base_amount` (impuestos encadenados)**: no estaba
        cubierto -- un impuesto con `include_base_amount=True` no
        encadenaba su monto a la base del siguiente impuesto en
        `round_per_line`. Corregido con `extra_base_by_line_id`,
        alimentado *solo* con montos ya calculados por línea dentro de
        este mismo bloque (nunca desde `base_line['tax_details']` del
        core, que se probó y se revirtió: usa un `rate` interno que
        puede estar obsoleto igual que `record.balance`, y regresionó
        test_30 durante el desarrollo). Los repartition lines se procesan
        ordenados por `tax.sequence` para que el impuesto que encadena se
        calcule antes que su dependiente. Cubre ambos modos
        (`round_per_line` vía `_per_line_tax_sums`, `round_globally` vía
        `_grouped_tax_sums` con distribución proporcional).
      - **Alcance por `amount_type` (decisión de negocio, no técnica)**:
        se verificó qué tipos de impuesto cubre el fix:
        - `percent`: cubierto (es el único tipo que Venezuela usa en la
          práctica).
        - `group` con hijos `percent`: cubierto automáticamente -- el
          core de Odoo expande el grupo en sus impuestos hijos antes de
          generar las repartition lines, así que cada hijo pasa
          individualmente por `_apply_vef_first` igual que un `percent`
          suelto. Verificado exacto contra el oráculo (`test_42`).
        - `fixed`: no necesita cobertura -- es un monto plano por unidad,
          sin multiplicación por base que pueda desalinearse entre modos.
          Confirmado que el modo no le afecta en absoluto (`test_40`).
        - `division`: **tiene el mismo bug que tenía `percent` antes de
          este fix, confirmado y sin corregir** (`test_41`, oráculo
          `compute_all()`: nativo `round_per_line` da 1.582,58 Bs, el
          método fiscal exige 1.576,33 Bs -- diverge 6,25 Bs, más que el
          error de céntimos de `percent`). **Decisión explícita: NO se
          cubre.** En Venezuela no se usa ningún tipo de impuesto fuera
          de porcentual (`percent`/`group` de hijos `percent`), así que
          `division` queda fuera de alcance a propósito, no por
          limitación técnica.
      - **Hallazgo de configuración (fuera del código, decisión de
        negocio)**: `company.tax_calculation_rounding_method` default en
        Odoo 19 es `round_globally`; este módulo/instalación **no** lo
        fuerza a `round_per_line` en ningún dato de instalación
        (`data/res_company_data.xml` no lo toca). Dado que Venezuela
        exige el método línea-por-línea (máquina fiscal) y que el único
        tipo de impuesto real (`percent`) ya está cubierto por este fix,
        **`round_per_line` debería ser el valor por defecto/requerido**
        para compañías venezolanas -- pendiente de decidir si se fuerza
        vía dato de instalación o se documenta como paso manual de
        configuración (no implementado en este fix, solo documentado).
      Tests: `test_35` (mezcla real de impuestos bajo `round_per_line`,
      hueco que tenían los tests 01-27 al correr solo en
      `round_globally`), `test_36`-`test_39` (comportamiento nativo por
      `amount_type`: `fixed`, `price_include`, `division`, y
      `price_include` a través de nuestro fix multi-moneda), `test_40`
      (prueba que el modo SÍ afecta a `division` -- vía el core, no vía
      este módulo -- y que NO afecta a `fixed`), `test_41`/`test_42`
      (oráculo `compute_all()` confirmando el bug sin corregir en
      `division` y la cobertura correcta en `group`)
- [x] 2.17 (seguimiento de 2.16, code review posterior) `_vef_base_for_tax`
      quedó definida pero sin ningún invocador: al escribir
      `_grouped_tax_sums` (rama `round_globally`, para soportar
      `include_base_amount` ahí también) se reimplementó la misma suma
      inline en vez de llamarla, y la función vieja nunca se borró.
      Eliminada (`grep` confirma cero referencias). Confirmado además,
      explícitamente, que `_per_line_tax_sums` (rama `round_per_line`)
      usa la misma `_effective_entries`/`extra_base_by_line_id` que
      `_grouped_tax_sums`, así que `include_base_amount` funciona en
      ambos modos por el mismo mecanismo -- ya cubierto por `test_33`
      (ambos modos, USD/EUR), no fue necesario un test nuevo. Suite
      completa re-verificada tras el cleanup: 205/205, 0 fallos.
- [x] 2.18 (code review del PR #1362) Dos hallazgos sobre la cobertura de tests de 2.14/2.15:
      (1) bloqueante -- `test_30`/`test_31` solo comparaban contra `inv.amount_tax`, que el
      core computa directo de las líneas reales vía `_compute_amount`, sin pasar nunca por
      `_get_tax_totals_summary` (donde vive `_fix_tax_amount_for_round_per_line`); y toda la
      suite corría en `out_invoice` con `abs()` en todos lados, sin ejercitar `direction_sign`
      en compras ni refunds. Agregados `test_43` (ejercita el campo real del widget/PDF,
      `inv.tax_totals`, en ambos modos de redondeo), `test_44` (factura de compra,
      `in_invoice`, `direction_sign == 1`) y `test_45` (nota de crédito, `out_refund`, usa
      `refund_repartition_line_ids`, también `direction_sign == 1`) -- las dos últimas
      revelaron que el signo de `direction_sign` es el opuesto al asumido inicialmente
      (`out_invoice`/`in_refund` = `-1`; `in_invoice`/`out_refund` = `1`, los tipos
      `is_outbound()` del core), corregido en los propios tests. (2) mejorable -- `test_32` y
      `test_34` (SCOPE CHECK de la factura VEF-only) solo logueaban, sin ninguna aserción que
      fallara ante una regresión. Convertidos a aserciones reales sobre valores fijados
      (`test_32`: `round_per_line`/`round_globally` dan 2.868,88/2.868,89 respectivamente, sin
      necesitar el fix multi-moneda porque el core ya redondea bien por línea en VEF puro;
      `test_34`: Tax A no encadenado se predice con el mismo oráculo de `test_33` en
      `round_per_line`, y se fija el valor observado en `round_globally` porque ahí Odoo
      redistribuye un céntimo entre las dos líneas de producto, lo que vuelve frágil una
      predicción "sumar y redondear una vez" en ese modo específico). Verificado corriendo
      los 45 tests de `l10n_ve_accountant_rounding` con `--addons-path` explícito contra el
      contenedor `odoo-binaural-19` (`docker-odoo`), en una base de datos descartable: 45/45,
      0 fallos.

## 3. `l10n_ve_sale`

- [x] 3.1 `foreign_rate_date`: campo nuevo, oculto en el formulario, con
      `default` propio (el ORM no ejecuta `_compute_rate` en `create` porque
      `foreign_rate` ya trae `default`)
- [x] 3.2 `_compute_rate` sella la fecha también en las ramas donde hace
      `continue`, para que la tasa congelada conserve su fecha
- [x] 3.3 `sale.order.line._compute_foreign_price`: usa `foreign_rate_date`,
      con `round=False` + `float_round`, y ramas duplicadas fusionadas
- [x] 3.4 `_compute_foreign_subtotal`: pasa por `compute_all`
- [x] 3.5 `_prepare_invoice`: pasa `foreign_rate_date` como `invoice_date`
- [x] 3.6 `_compute_amount_signed` y los totales alternos: se leen de
      `tax_totals`
- [x] 3.7 Corregido el doble `@api.depends` en `_compute_foreign_total_billed`,
      que anulaba las dependencias reales dejando solo `tax_totals`
- [x] 3.8 Multi-compañía: las decisiones se toman con `company_id` de la
      orden, no con `env.company`
- [x] 3.9 Eliminado `_update_invoices_rate`: código muerto, sin invocadores en
      ningún repo
- [x] 3.10 Migración `19.0.1.0.6/post-set_foreign_rate_date.py` para las
      órdenes existentes no facturadas

## 4. `binaural_purchase` (integra-addons, sin openspec)

- [x] 4.1 `_compute_foreign_price`: `round=False` + `float_round`, guard de
      `currency_id` vacío, ramas duplicadas fusionadas
- [x] 4.2 `_compute_foreign_subtotal`: pasa por `compute_all`
- [x] 4.3 `_compute_tax_totals`: restaurada la inyección de
      `active_id`/`active_model`, como en `account.move` y `sale.order`
- [x] 4.4 Totales alternos y `_compute_amount_signed`: desde `tax_totals`
- [x] 4.5 El onchange deja de forzar `foreign_price`: lo recalcula el compute
- [x] 4.6 Limpieza: dos tests renombrados (el nombre afirmaba lo contrario de
      lo que verificaban), test de traducciones eliminado, `.po` con salto de
      línea final, contenedor de la vista renombrado

## 5. Verificación

- [x] 5.1 `l10n_ve_accountant`: 32 tests, 0 fallos
- [x] 5.2 `l10n_ve_sale`: 20 tests, 0 fallos
- [x] 5.3 `binaural_purchase`: 43 tests, 0 fallos
- [x] 5.4 16 tests nuevos, cada uno construido para fallar si se revierte el
      cambio que verifica
- [ ] 5.5 Validación funcional contra el ejemplo del ticket (Bs 6.215,30 /
      12.430,60 / total 21.629,24) — pendiente, la tarea está en
      "Validación - BIN"
- [ ] 5.6 `openspec validate --changes`

## 6. Fuera de alcance, inventariado aparte

- [ ] 6.1 Dirección de conversión invertida en `binaural_hr_payroll`
      (`get_vef_wage` devuelve USD y sale impreso en cuatro plantillas de
      recibo)
- [ ] 6.2 Doble multiplicación por la tasa en
      `binaural_advance_payment_igtf` sobre la base imponible de IGTF
- [ ] 6.3 Impresión fiscal: `l10n_ve_account_mf`, `binaural_ft`,
      `binaural_club_socios_mf` — requieren notificación previa
- [ ] 6.4 Limpieza de restos v17: montos alternos de retención, ramas muertas
      de `l10n_ve_invoice_digital`, `l10n_ve_iot_mf` marcado como no
      instalable, y `legacy_compute_line_ids_foreign_debit_and_credit` con su
      `TypeError` y su acción de servidor
