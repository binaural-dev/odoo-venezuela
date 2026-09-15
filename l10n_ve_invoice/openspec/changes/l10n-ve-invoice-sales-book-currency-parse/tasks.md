## 1. Fix del parseo

- [x] 1.1 `wizard/accounting_reports.py`, `convert_currency_to_float`: eliminar
      el `split('\xa0')[0]` (se quedaba con el símbolo "Bs." y perdía el monto);
      dejar que la regex descarte símbolo/espacios y la regla punto-de-miles
      limpie el punto sobrante. Verificado leyendo el diff.
- [x] 1.2 Bump de manifest `19.0.1.0.13` → `19.0.1.0.14`.

## 2. Tests

- [x] 2.1 `tests/test_accounting_reports.py`: casos símbolo-antes con `\xa0`
      (`"Bs.\xa0876,18"` → 876.18; `"Bs.\xa00,00"` → 0.0), miles+decimales
      (`"Bs.\xa02.382,11"` → 2382.11; `"Bs.\xa013.836,97"` → 13836.97),
      símbolo-después coma-decimal (`"1.234,56\xa0Bs."` → 1234.56) y
      símbolo-después punto-decimal Bs.F (`"100.00\xa0Bs.F"` → 100.0). Los 4
      tests previos (`""`, `None`, `"Bs0.00"`, `"ABC"`) siguen pasando.
- [x] 2.2 Regresión detectada por CI: el `test_amount_taxeds_no_deductible`
      base usa formato `"100.00\xa0Bs.F"` (símbolo después, decimal de punto).
      La primera versión del fix (quitar el `split('\xa0')`) dejaba el punto de
      `"Bs.F"` colándose → 0.0 → `assertGreater` fallaba. Reescrito el parseo
      para quedarse con el token numérico y descartar el símbolo completo. Bump
      versión → 19.0.1.0.16.

## 3. Verificación manual (en 2doce, período 1–15 sep)

- [ ] 3.1 Actualizar `l10n_ve_invoice` y generar el Libro de Ventas del período:
      ya no debe inundar el log con el warning de conversión ni cortar la
      conexión.
- [ ] 3.2 Confirmar que el resumen del pie ya no sale en cero y cuadra con las
      líneas del cuerpo.

## 4. Rendimiento (segunda iteración)

Tras el fix del parseo, 2doce seguía muriendo por `CPU time limit exceeded`
(`limit_time_cpu=60`) con 4690 asientos: `_determinate_amount_taxeds` se
invocaba ~17× por asiento (1 en el cuerpo + ~16 en el resumen).

- [x] 4.1 Memoizar `_determinate_amount_taxeds` por `move.id` durante una
      generación del libro, vía cache en el contexto (`_ve_book_amounts_cache`),
      sembrado por `generate_sales_book` / `generate_purchases_book`. Sin cambios
      de firma (no rompe overrides de payment_extension / third_party_invoice).
- [x] 4.2 Verificado que el dict devuelto solo se lee (no se muta), así que
      devolver el mismo objeto cacheado es seguro. Bump versión → 19.0.1.0.15.
- [ ] 4.3 Validar en 2doce (1–15 sep) que el libro completa sin exceder el CPU
      time limit. Si aún queda al límite, subir `LIMIT_TIME_CPU` de la instancia
      (ops) da el margen restante.
