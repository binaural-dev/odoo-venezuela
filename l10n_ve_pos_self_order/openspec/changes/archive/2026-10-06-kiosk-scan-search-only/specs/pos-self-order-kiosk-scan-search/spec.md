# Spec delta: pos-self-order-kiosk-scan-search

## ADDED Requirements

### Requirement: Ajuste opcional "solo escaneo / búsqueda" por punto de venta

El punto de venta SHALL exponer un ajuste booleano
`self_ordering_hide_catalog`, editable en Ajustes solo cuando el modo de
autopedido es `kiosk`. El ajuste SHALL enviarse al frontend del Kiosko. Con el
ajuste desactivado, el Kiosko SHALL comportarse igual que el nativo (catálogo
visible, sin saludo ni buscador).

#### Scenario: Ajuste visible solo en modo Kiosko

- **GIVEN** la pantalla de Ajustes de un punto de venta
- **WHEN** el modo de autopedido es `kiosk`
- **THEN** se muestra el ajuste "Kiosko: solo escaneo / búsqueda"
- **WHEN** el modo es distinto de `kiosk`
- **THEN** el ajuste no se muestra

#### Scenario: Sin el ajuste, catálogo nativo

- **GIVEN** un Kiosko con `self_ordering_hide_catalog` desactivado
- **WHEN** el cliente llega a la lista de productos
- **THEN** ve el catálogo completo (categorías + grilla) sin saludo ni buscador

### Requirement: Ocultar el catálogo y ofrecer buscador en el Kiosko

La página de lista de productos del Kiosko SHALL ocultar el catálogo y ofrecer un buscador cuando el modo es `kiosk` y `self_ordering_hide_catalog` está activo.
Con el ajuste activo SHALL ocultar la barra de categorías, la de subcategorías
y la grilla del catálogo, y SHALL mostrar un buscador de texto. El buscador
SHALL filtrar los `product.template` disponibles (`self_order_available`) por
nombre, `display_name`, código de barras o referencia interna, con un tope de
resultados. Los resultados SHALL renderizarse con las mismas tarjetas del
catálogo, y tocar un resultado SHALL añadirlo al carrito con el mismo
comportamiento que el catálogo (incluidos combos y productos configurables).

#### Scenario: Catálogo oculto

- **GIVEN** un Kiosko con el ajuste activo
- **WHEN** el cliente llega a la lista de productos
- **THEN** no se muestran las categorías ni la grilla del catálogo, y sí un
  buscador de texto

#### Scenario: Buscar por nombre o código

- **GIVEN** el buscador visible
- **WHEN** el cliente escribe parte del nombre, código de barras o referencia de
  un producto disponible
- **THEN** se muestran los productos coincidentes (hasta el tope) como tarjetas
- **WHEN** ninguna coincide
- **THEN** se muestra el mensaje de "sin resultados"

#### Scenario: Añadir desde un resultado

- **GIVEN** una tarjeta de resultado de búsqueda
- **WHEN** el cliente la toca
- **THEN** el producto se añade al carrito igual que en el catálogo (los combos
  y configurables abren su paso correspondiente), y el buscador se limpia tras
  añadir un producto simple

### Requirement: Escaneo por lector siempre disponible y sin salir de la pantalla

El escaneo por lector de código de barras SHALL seguir funcionando en el modo
"solo escaneo / búsqueda" (buscar por `barcode` y añadir al pedido). A
diferencia del Kiosko nativo, escanear NO SHALL navegar al carrito: el cliente
SHALL permanecer en la pantalla de escaneo/búsqueda, donde el producto aparece
en el resumen en-sitio. Ocultar el catálogo NO SHALL deshabilitar el escaneo.

#### Scenario: Escanear con el catálogo oculto

- **GIVEN** un Kiosko con el ajuste activo y un lector de código de barras
- **WHEN** el cliente escanea un producto disponible
- **THEN** el producto se añade al pedido y el cliente permanece en la pantalla
  de escaneo/búsqueda (no salta al carrito)

### Requirement: Pago directo sin pasar por el carrito

El botón de pago del modo escaneo/búsqueda SHALL llevar directamente a la pantalla de métodos de pago, omitiendo la pantalla intermedia de resumen del pedido (carrito).
Esta omisión SHALL aplicar solo cuando el catálogo está oculto. También SHALL
ejecutar las mismas validaciones que el carrito nativo (verificación de
disponibilidad y de datos del cliente) antes de proceder. Si faltaran datos
requeridos del cliente, SHALL recurrir al flujo completo del carrito para
recogerlos.

#### Scenario: Pagar salta al pago

- **GIVEN** un pedido con líneas en la pantalla de escaneo/búsqueda y un cliente
  identificado
- **WHEN** el cliente pulsa el botón de pago
- **THEN** va directamente a la pantalla de métodos de pago, sin mostrar el
  resumen/carrito intermedio

#### Scenario: Datos incompletos recurren al carrito

- **GIVEN** un pedido cuyo cliente no cumple los datos requeridos
- **WHEN** el cliente pulsa el botón de pago
- **THEN** se abre el flujo completo del carrito para completar la información

### Requirement: Resumen del pedido en-sitio

Cuando el catálogo está oculto y el cliente no está buscando, la pantalla SHALL
mostrar el resumen del pedido actual en el área central (donde de otro modo iría
la pista de escaneo). Cada línea SHALL mostrar nombre, cantidad y precio, con
controles para aumentar/disminuir la cantidad y eliminar la línea. El resumen
SHALL actualizarse en vivo al escanear o añadir productos. Si hay una búsqueda
activa, SHALL mostrarse en su lugar la grilla de resultados.

#### Scenario: El pedido aparece al añadir

- **GIVEN** un Kiosko con el ajuste activo y sin búsqueda activa
- **WHEN** el cliente escanea o añade un producto
- **THEN** el producto aparece en el resumen del pedido en el área central

#### Scenario: Editar cantidades desde el resumen

- **GIVEN** una línea en el resumen en-sitio
- **WHEN** el cliente aumenta/disminuye la cantidad o elimina la línea
- **THEN** el resumen y los totales se actualizan en consecuencia

#### Scenario: La búsqueda tiene prioridad sobre el resumen

- **GIVEN** un pedido con líneas
- **WHEN** el cliente escribe en el buscador
- **THEN** se muestran los resultados de búsqueda (para añadir), no el resumen

### Requirement: Saludo personalizado al cliente identificado

Cuando el modo es `kiosk` y el catálogo está oculto, la página SHALL mostrar
arriba un saludo "¡Hola {nombre}!" usando el nombre del contacto del pedido
actual (`currentOrder.partner_id`). Si no hubiera nombre, SHALL mostrar un
saludo genérico ("¡Hola!"). El texto SHALL ser traducible vía `_t()`.

#### Scenario: Cliente identificado por cédula

- **GIVEN** un Kiosko con el ajuste activo donde el cliente ya se identificó por
  cédula al inicio
- **WHEN** llega a la lista de productos
- **THEN** ve "¡Hola {nombre del contacto}!" encima del buscador

#### Scenario: Sin nombre disponible

- **GIVEN** un pedido sin contacto con nombre
- **WHEN** se muestra la página con el catálogo oculto
- **THEN** se muestra el saludo genérico "¡Hola!"
