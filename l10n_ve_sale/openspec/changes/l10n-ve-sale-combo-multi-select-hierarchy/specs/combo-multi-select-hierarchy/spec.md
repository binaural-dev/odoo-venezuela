# Spec delta: combo-multi-select-hierarchy

## ADDED Requirements

### Requirement: Selección múltiple por opción de combo

El configurador de combo (`sale.order_line._onchange_order_line`) SHALL
aceptar una o más elecciones por `product.combo` (opción), en vez de exigir
exactamente una. La línea real del combo (`product_id` = producto tipo
`combo`) SHALL permanecer sin `display_type`: nunca se convierte en sección,
por el `CHECK` de Postgres que lo impide.

#### Scenario: Elegir dos productos en la misma opción

- **GIVEN** un combo con una opción que tiene 2+ productos candidatos
- **WHEN** el usuario elige 2 de esos productos en el wizard y confirma
- **THEN** se crean 2 líneas, cada una con su propio `combo_item_id`
- **AND** la línea raíz del combo sigue siendo una línea de producto normal

### Requirement: Jerarquía decorativa por campos propios

Cada línea que pertenezca a un combo (raíz, subsección u ítem) SHALL tener
`combo_tagged = True`. La raíz y los ítems SHALL tener `combo_root_line_id`
apuntando a la raíz. Una subsección decorativa (`line_subsection`, sin
`combo_item_id`) SHALL crearse por cada opción con más de un candidato
elegible, y los ítems de esa opción SHALL tener `combo_parent_line_id`
apuntando a ella.

#### Scenario: Combo con una sola opción

- **GIVEN** un combo con una única opción
- **WHEN** se confirma la selección
- **THEN** NO se crea ninguna subsección decorativa
- **AND** los ítems cuelgan directo de la raíz (`combo_parent_line_id` =
  raíz)

### Requirement: Reconstrucción de la jerarquía con ids reales tras guardar

Un Many2one que apunta a otra línea creada en el MISMO lote (todo el árbol
de un combo nuevo, en un documento que se guarda por primera vez) SHALL NO
confiarse para persistir correctamente durante el onchange. `sale.order`
SHALL reconstruir `combo_parent_line_id`/`combo_root_line_id` con los ids ya
reales, inmediatamente después de `create()`/`write()`.

#### Scenario: Guardar un combo nuevo con jerarquía completa

- **GIVEN** una cotización nueva con un combo de 2+ opciones, cada una con
  2+ productos elegidos
- **WHEN** se guarda la cotización por primera vez
- **THEN** TODAS las líneas del árbol (raíz, subsecciones, ítems) tienen
  `combo_parent_line_id`/`combo_root_line_id` poblados con ids reales,
  ninguno en `NULL`

#### Scenario: Eliminar un combo sin guardar primero

- **GIVEN** un combo recién agregado a una cotización sin guardar
- **WHEN** el usuario lo elimina y guarda el documento
- **THEN** el guardado NO lanza `InvalidTextRepresentation` sobre un id
  virtual del cliente

### Requirement: Productos ajenos al combo nunca se cuentan como parte de él

Un producto agregado por fuera del combo (botón global "Agregar un
producto", o el configurador nativo de "productos opcionales" abierto tras
confirmar el combo) SHALL terminar posicionado después del último
descendiente del árbol del combo, nunca intercalado entre sus líneas, y
SHALL NO tener `combo_tagged = True`.

#### Scenario: Agregar un producto opcional justo después de confirmar el combo

- **GIVEN** un combo con subsecciones ya armado
- **WHEN** se agrega un producto opcional desde el configurador nativo que
  se abre tras confirmar el combo
- **THEN** ese producto queda posicionado después del último ítem real del
  combo, bajo una sección separadora "Productos Adicionales"
- **AND** el subtotal mostrado junto a cualquier subsección del combo NO lo
  incluye

### Requirement: Kebab y arrastre bloqueados para filas de un combo

Toda fila que pertenezca a un combo (raíz, subsección o ítem) SHALL
mostrar únicamente la opción "Eliminar" en su menú kebab, y SHALL NO poder
arrastrarse ni recibir un drop de otra fila junto a ella.

#### Scenario: Kebab de una subsección de combo

- **GIVEN** una subsección decorativa de un combo
- **WHEN** se abre su menú kebab
- **THEN** la única opción visible es "Eliminar"

### Requirement: Reparto de precio del combo por tipo de ítem

Cada `product.combo.item` SHALL tener un `item_type`
(`principal`/`percentage`/`fixed_price`). El precio del combo SHALL
repartirse: primero los ítems `fixed_price` (su propio `lst_price`,
convertido a la moneda de la orden), luego los `percentage` (un % de lo que
queda), y el resto en partes iguales entre los ítems `principal` **por
línea**, no ponderado por cantidad.

#### Scenario: Ítem principal con cantidad mayor a 1

- **GIVEN** dos ítems `principal` en la misma opción, uno con cantidad 1 y
  otro con cantidad 3
- **WHEN** se calcula el precio de cada uno
- **THEN** ambos reciben el mismo `price_unit` (reparto por línea, no por
  unidad)
- **AND** el total resultante del combo puede no coincidir con su
  `list_price` cuando las cantidades difieren de 1 (comportamiento
  aceptado explícitamente, no es un defecto a corregir en este cambio)

### Requirement: Combo en `account.move` con la misma jerarquía

El combo SHALL poder configurarse en una factura directa y SHALL conservarse
cuando la factura se crea desde una orden. En `account.move` la raíz del combo
SHALL ser una `line_section` con `combo_tagged = True` y `product_id` vacío;
subsecciones (`line_subsection`) y productos SHALL tener `combo_tagged = True`.
Al crear la factura desde una orden, `combo_parent_line_id`/`combo_root_line_id`
SHALL reconstruirse con ids reales justo después de crearla.

#### Scenario: Configurar un combo en una factura directa

- **GIVEN** una factura de cliente en borrador
- **WHEN** el usuario elige un producto tipo combo y confirma el wizard
- **THEN** la línea se convierte en sección raíz con el nombre del combo en
  MAYÚSCULAS
- **AND** se crean las subsecciones y productos elegidos, con cantidad =
  cantidad del combo × cantidad por combo

#### Scenario: Facturar una orden con combo

- **GIVEN** una orden confirmada con un combo de 2+ opciones
- **WHEN** se crea la factura desde la orden
- **THEN** la sección raíz se llama solo `<COMBO>` (sin sufijo `x <cantidad>`)
- **AND** todas las líneas del árbol tienen `combo_tagged = True` y su
  jerarquía poblada con ids reales

### Requirement: Presentación jerárquica del combo

Los nombres de la raíz, secciones y subsecciones de un combo SHALL mostrarse
en MAYÚSCULAS. Las subsecciones SHALL mostrarse con sangría de nivel 1 y los
productos con sangría de nivel 2, mediante CSS (no con espacios en el nombre).
Las filas de un combo SHALL NO mostrar el control de arrastre.

#### Scenario: Orden con combo de dos opciones

- **GIVEN** una orden con un combo de 2 opciones ya guardada
- **WHEN** se abre en el formulario
- **THEN** las subsecciones aparecen indentadas bajo la raíz y los productos
  más indentadas bajo su subsección
- **AND** ninguna fila del combo muestra el `::` de arrastre

### Requirement: Traducciones y propiedad de `item_type`/`percentage`

`product.combo.item.item_type` y `percentage` SHALL definirse únicamente en
`l10n_ve_sale`; `binaural_clinics_sale` SHALL NO redefinirlos. Sus
traducciones es_VE ("Tipo de opción", "Porcentaje", "Precio fijo", …) SHALL
estar en `l10n_ve_sale/i18n/es_VE.po`.

#### Scenario: Instalar `binaural_clinics_sale` con `l10n_ve_sale`

- **GIVEN** una base con ambos módulos
- **WHEN** se actualiza `binaural_clinics_sale`
- **THEN** los campos y el reparto de precio siguen funcionando, provistos por
  `l10n_ve_sale`
