## 1. Fix del parseo

- [x] 1.1 `wizard/accounting_reports.py`, `convert_currency_to_float`: eliminar
      el `split('\xa0')[0]` (se quedaba con el símbolo "Bs." y perdía el monto);
      dejar que la regex descarte símbolo/espacios y la regla punto-de-miles
      limpie el punto sobrante. Verificado leyendo el diff.
- [x] 1.2 Bump de manifest `19.0.1.0.13` → `19.0.1.0.14`.

## 2. Tests

- [x] 2.1 `tests/test_accounting_reports.py`: casos símbolo-antes con `\xa0`
      (`"Bs.\xa0876,18"` → 876.18; `"Bs.\xa00,00"` → 0.0), miles+decimales
      (`"Bs.\xa02.382,11"` → 2382.11; `"Bs.\xa013.836,97"` → 13836.97) y
      símbolo-después (`"1.234,56\xa0Bs."` → 1234.56). Los 4 tests previos
      (`""`, `None`, `"Bs0.00"`, `"ABC"`) siguen pasando.

## 3. Verificación manual (en 2doce, período 1–15 sep)

- [ ] 3.1 Actualizar `l10n_ve_invoice` y generar el Libro de Ventas del período:
      ya no debe inundar el log con el warning de conversión ni cortar la
      conexión.
- [ ] 3.2 Confirmar que el resumen del pie ya no sale en cero y cuadra con las
      líneas del cuerpo.

## 4. Follow-up (fuera de alcance)

- [ ] 4.1 Memoización de `_determinate_amount_taxeds` por asiento, solo si tras
      el fix del parseo el período grande sigue lento (con el log ya limpio,
      `tax_totals` ya lo cachea el ORM).
