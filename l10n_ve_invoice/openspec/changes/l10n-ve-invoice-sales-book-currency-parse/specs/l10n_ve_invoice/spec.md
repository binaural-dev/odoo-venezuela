## ADDED Requirements

### Requirement: Importes del libro leídos crudos, independientes del idioma
El Libro de Compras/Ventas DEBE (MUST) obtener los importes de cada asiento
(`_determinate_amount_taxeds`) a partir de los valores numéricos crudos de
`move.tax_totals` (`base_amount` / `tax_amount`, en VES), NO re-parseando los
string `formatted_*_currency_ves`. El resultado NO debe depender del idioma del
usuario que dispara el reporte (el formateo de `formatLang` usa ese idioma, así
que su separador decimal varía).

#### Scenario: Usuario con idioma de decimal-punto
- **WHEN** un usuario con la interfaz en inglés (decimal `.`, miles `,`) genera el
  libro de un asiento cuya base imponible es `1234.56` VES
- **THEN** el libro reporta `1234.56` (y no `1.23456` ni `0.0`)

#### Scenario: Usuario con idioma es_VE
- **WHEN** un usuario en es_VE (decimal `,`, miles `.`) genera el mismo libro
- **THEN** el libro reporta el mismo `1234.56`

### Requirement: Memoización de importes por asiento durante la generación
`_determinate_amount_taxeds` DEBE (MUST) calcularse a lo sumo una vez por asiento
durante una misma generación del libro, aunque el cuerpo y el resumen lo
consulten muchas veces.

#### Scenario: El resumen no recalcula por línea
- **WHEN** se genera un libro cuyo resumen tiene varias líneas que recorren los
  mismos asientos
- **THEN** el importe de cada asiento se calcula una sola vez (cache por
  `move.id` en el contexto), y el valor cacheado es igual al calculado en el cuerpo
