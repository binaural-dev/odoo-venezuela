# Fix: importes del Libro de Compras/Ventas leídos crudos (no re-parseados)

## Why

Ticket Helpdesk #15026 (validación en 2doce). Al generar el Libro de Ventas de
un período con muchos registros (1–15 sep, 4690 asientos), el reporte fallaba de
dos formas encadenadas:

1. El log se inundaba de miles de líneas y los totales del pie salían en cero:

   ```
   WARNING ... No se pudo convertir la cadena de moneda 'Bs. 876,18' a float.
   Valor final procesado: '.'
   ```

2. Tras mitigar eso, el worker moría por `Exception: CPU time limit exceeded`.

**Causa raíz común:** `_determinate_amount_taxeds` tomaba los importes ya
**formateados** desde `move.tax_totals` (`formatted_base_amount_currency_ves`,
`formatted_tax_amount_currency_ves`) y los **re-parseaba** a `float` con
`convert_currency_to_float`. Eso es frágil y caro:

- **Frágil / dependiente del idioma:** esos string los arma `formatLang`, que usa
  el idioma del **usuario** que dispara el reporte, no el de la compañía. En
  es_VE el decimal es coma; con un usuario en inglés es punto. El parser no puede
  adivinar el separador sin equivocarse, y una heurística fija produce importes
  **silenciosamente errados** (p.ej. dividir entre 1000) en un libro que va al
  SENIAT. La versión original además se quedaba con el lado equivocado al partir
  por el espacio no-separable `\xa0`, devolviendo `0.0` en todos los importes VES.
- **Caro:** `_determinate_amount_taxeds` se invoca ~1 vez por asiento en el cuerpo
  y ~16 veces por asiento en el resumen (`_determinate_resume_books` corre una vez
  por línea de resumen y recorre todos los asientos), ~17× por asiento. Formatear
  + re-parsear en cada una, ~80k veces, era el grueso del costo de CPU.

El float crudo (`base_amount` / `tax_amount`, ya en VES) **está en el mismo dict**
de `tax_totals`: es exactamente el valor que `l10n_ve_accountant` formatea para
producir los `formatted_*_currency_ves` (`models/account_tax.py:213-222`,
`:273-282`, `:328-337`). Leerlo directo mata las dos causas de raíz.

## What Changes

- **`wizard/accounting_reports.py`, `_determinate_amount_taxeds` (fix principal):**
  se leen los importes crudos `base_amount` / `tax_amount` de `tax_totals` (a
  nivel top y por `tax_group`) en vez de re-parsear los `formatted_*_currency_ves`
  (`:1036-1037`, `:1094-1095`). Elimina la dependencia del idioma, los ceros y el
  grueso del costo de CPU.
- **Memoización** de `_determinate_amount_taxeds` por `move.id` durante una
  generación del libro, para no repetir el cálculo ~17× por asiento. El cache vive
  en el contexto (`_ve_book_amounts_cache`, porque los recordsets no admiten
  atributos por `__slots__`) y lo siembran los entrypoints `generate_sales_book` /
  `generate_purchases_book` con `self.with_context(...)`. No cambia ninguna firma
  → no rompe los overrides de `l10n_ve_payment_extension` /
  `binaural_third_party_invoice`. El dict devuelto solo se consume en lectura
  (`_fields_sale_book_line` arma un dict nuevo; `_determinate_resume_books` solo
  suma), así que devolver el mismo objeto cacheado es seguro.
- `convert_currency_to_float`: queda endurecido (parseo por token) pero **ya no se
  usa en el camino del libro**; se conserva como utilidad.
- `tests/test_accounting_reports.py`: casos de `convert_currency_to_float`. Los
  tests existentes de `_determinate_amount_taxeds` cubren la ruta de lectura cruda.
- `__manifest__.py`: versión `19.0.1.0.13` → `19.0.1.0.16`.

## Non-goals

- **Rendimiento en producción sin validar aún:** la medición previa se hizo con
  `LIMIT_TIME_CPU` subido a 300 **solo en la instancia local** (cambio de ops, no
  de este PR). Falta re-medir con el límite de producción (60s) y este código.
- **Controlador `/web/download_sales_book`:** escalado a superusuario, `company_id`
  del query string sin validar y `search([], limit=1)` sobre el último wizard de
  cualquier usuario. Pre-existente; queda para un ticket aparte de seguridad /
  multi-compañía.
- **`UserError` por asiento sin `invoice_date_display`:** hoy aborta el libro
  entero (`_fields_sale_book_line:68`). Ahora que #1270 mete facturas de máquina
  fiscal/PdV al libro conviene evaluar degradarlo a línea omitida + warning; fuera
  de alcance de este fix.
