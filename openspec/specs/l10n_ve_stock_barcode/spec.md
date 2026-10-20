# l10n_ve_stock_barcode

## Purpose

Módulo de traducción para la app de códigos de barras de inventario: provee la traducción al español de Venezuela de los términos del módulo estándar `stock_barcode`. No agrega modelos, vistas ni datos; su contenido es únicamente el archivo de traducciones `i18n/es_VE.po`.

## Requirements

### Requirement: Traducción es_VE de la app de códigos de barras

El módulo DEBE (MUST) proveer en `i18n/es_VE.po` un catálogo de traducciones al español de Venezuela cuyas entradas están atribuidas al módulo `stock_barcode` (así lo declara la cabecera del archivo y los comentarios `#. module: stock_barcode`), de modo que al cargarlas los usuarios con ese idioma vean traducida la interfaz de códigos de barras. La cobertura es parcial: de las 337 entradas del archivo, 67 tienen `msgstr` vacío y por lo tanto siguen mostrándose en inglés.

#### Scenario: Usuario con idioma español (Venezuela)

- **WHEN** un usuario con idioma `es_VE` usa la app de códigos de barras con el módulo instalado
- **THEN** los términos de `stock_barcode` con traducción no vacía en el archivo se muestran traducidos

#### Scenario: Término sin traducir en el catálogo

- **WHEN** el término corresponde a una de las entradas con `msgstr` vacío
- **THEN** la interfaz lo muestra en su idioma original

### Requirement: Instalación automática junto a la app de códigos de barras

El módulo DEBE (MUST) declararse con `auto_install` en su manifest y depender únicamente de `stock_barcode`, de modo que se instale automáticamente cuando `stock_barcode` está instalado.

#### Scenario: Instalación de stock_barcode

- **WHEN** se instala el módulo `stock_barcode` en la base de datos
- **THEN** `l10n_ve_stock_barcode` se instala automáticamente
