## 1. Leer importes crudos (fix principal)

- [x] 1.1 `wizard/accounting_reports.py`, `_determinate_amount_taxeds`: leer
      `base_amount` / `tax_amount` crudos de `tax_totals` (top y por `tax_group`,
      `:1036-1037`, `:1094-1095`) en vez de re-parsear los
      `formatted_*_currency_ves`. Elimina la dependencia del idioma del usuario
      (importes silenciosamente errados con UI en inglés), los ceros y el grueso
      del costo de CPU. Verificado que el crudo es el valor VES que
      `l10n_ve_accountant` formatea (`models/account_tax.py:213-222`, etc.).
- [x] 1.2 `convert_currency_to_float` queda fuera del camino del libro (se
      conserva endurecido como utilidad). Bump manifest → `19.0.1.0.16`.

## 2. Rendimiento (memoización)

`_determinate_amount_taxeds` se invoca ~17× por asiento (1 cuerpo + ~16 resumen).

- [x] 2.1 Memoizar por `move.id` durante una generación del libro, vía cache en el
      contexto (`_ve_book_amounts_cache`; los recordsets no admiten atributos por
      `__slots__`), sembrado por `generate_sales_book` / `generate_purchases_book`.
      Sin cambios de firma (no rompe overrides de payment_extension /
      third_party_invoice).
- [x] 2.2 Verificado que el dict devuelto solo se lee (no se muta), así que
      devolver el mismo objeto cacheado es seguro.

## 3. Tests

- [x] 3.1 `tests/test_accounting_reports.py`: casos de `convert_currency_to_float`
      (utilidad). Los tests existentes de `_determinate_amount_taxeds`
      (`:461-560`) ejercitan la lectura cruda con el formato del entorno de test
      (`"100.00\xa0Bs.F"`).
- [ ] 3.2 Follow-up: test end-to-end de `generate_sales_book` (cuerpo + resumen)
      con máquina fiscal, y test de la memoización (valor cacheado == calculado,
      no contaminación entre asientos).

## 4. Verificación manual (en 2doce, período 1–15 sep, con este código)

- [ ] 4.1 Generar el Libro de Ventas del período: el log ya no debe inundarse con
      el warning de conversión.
- [ ] 4.2 El resumen del pie ya no sale en cero y cuadra con las líneas del cuerpo.
- [ ] 4.3 Re-medir con el `LIMIT_TIME_CPU` de producción (60s), NO con el 300
      subido en local: confirmar que el libro completa dentro del límite.
