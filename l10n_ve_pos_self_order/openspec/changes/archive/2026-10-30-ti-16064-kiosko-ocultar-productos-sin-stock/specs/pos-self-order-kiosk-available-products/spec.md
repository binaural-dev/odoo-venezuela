# Spec delta: pos-self-order-kiosk-available-products

## ADDED Requirements

### Requirement: El autopedido no carga almacenables sin stock con "Mostrar solamente los productos disponibles"

Con `pos_show_just_products_with_available_qty` activo en la compañía de la
caja, el autopedido (Kiosko y móvil) SHALL no cargar los productos
almacenables (`is_storable`) sin ninguna variante con stock a mano positivo en
la ubicación de origen del tipo de operación de la caja y sus hijas. Lo no
almacenable SHALL cargarse igual. Con el ajuste apagado la carga SHALL ser la
nativa.

#### Scenario: Almacenable sin stock

- **GIVEN** un Kiosko con el ajuste activo y un almacenable con stock a mano 0
  o negativo en su ubicación de origen
- **WHEN** el Kiosko carga sus datos
- **THEN** el producto y sus variantes no se cargan
- **AND** no sale en la cuadrícula ni en el buscador, y al escanearlo el Kiosko
  responde "No se encontró el producto"

#### Scenario: Stock en la ubicación de origen o sus hijas

- **GIVEN** un Kiosko con el ajuste activo y un almacenable con stock positivo
  en una ubicación hija de su ubicación de origen
- **WHEN** el Kiosko carga sus datos
- **THEN** el producto se carga

#### Scenario: Basta una variante con stock

- **GIVEN** un Kiosko con el ajuste activo y un almacenable con dos variantes,
  solo una con stock en la ubicación de origen
- **WHEN** el Kiosko carga sus datos
- **THEN** se cargan el producto y sus dos variantes

#### Scenario: Stock de otro almacén

- **GIVEN** un Kiosko con el ajuste activo y un almacenable con stock solo en
  otro almacén
- **WHEN** el Kiosko carga sus datos
- **THEN** el producto no se carga

#### Scenario: Lo no almacenable se carga sin stock

- **GIVEN** un Kiosko con el ajuste activo
- **WHEN** carga un servicio y un consumible sin control de stock, ambos sin
  stock
- **THEN** los dos se cargan

#### Scenario: Ajuste apagado

- **GIVEN** un Kiosko sin el ajuste
- **WHEN** carga sus datos
- **THEN** el almacenable sin stock se carga, como en el Kiosko nativo

#### Scenario: Carga real por la ruta pública

- **GIVEN** un Kiosko con el ajuste activo
- **WHEN** carga sus datos por la ruta pública, con el usuario por defecto del
  Kiosko y sin privilegios de superusuario
- **THEN** recibe el ajuste y los productos no almacenables, y no recibe el
  almacenable sin stock

### Requirement: Opciones de combo sin stock

Con el ajuste activo, una almacenable sin stock que el core carga como opción
de un combo SHALL llegar con `self_order_available = False`. El Kiosko SHALL no
mostrar en la cuadrícula (en ninguna categoría) ni en el buscador los
almacenables con `self_order_available = False`, SHALL no dejar elegirlos en el
combo y SHALL responder "no disponible" al escanearlos. El combo y sus
opciones con stock SHALL seguir disponibles.

#### Scenario: Opción sin stock

- **GIVEN** un Kiosko con el ajuste activo y un combo con una opción
  almacenable sin stock y otra con stock
- **WHEN** el cliente abre la cuadrícula y el combo
- **THEN** la opción sin stock no sale en la cuadrícula
- **AND** en el combo sale como "Agotado" y no se puede elegir, y la otra sí
- **AND** al escanearla el Kiosko responde "El producto no está disponible"

#### Scenario: Opción sin stock con categoría de PdV

- **GIVEN** un Kiosko con el ajuste activo y una opción de combo almacenable sin
  stock con una categoría de PdV
- **WHEN** el cliente abre esa categoría
- **THEN** la opción no sale
- **AND** una categoría de primer nivel que solo tenga opciones así no sale como
  pestaña
- **AND** una subcategoría así sigue en la barra de subcategorías y abre una
  cuadrícula vacía, como el Kiosko nativo con cualquier subcategoría vacía

#### Scenario: Almacenable desmarcado a mano para autopedido

- **GIVEN** un Kiosko con el ajuste activo y una opción de combo almacenable
  con stock a la que un gerente le quitó "Disponible en autopedido"
- **WHEN** el cliente abre la cuadrícula
- **THEN** la opción no sale (el Kiosko nativo la mostraría como "Agotado")

#### Scenario: Combo que no se puede completar

- **GIVEN** un Kiosko con el ajuste activo y un combo con una sola opción por
  grupo, almacenable y sin stock
- **WHEN** el cliente lo agrega
- **THEN** el Kiosko lo pasa directo al carrito sin la página del combo
- **AND** al pagar el core lo quita con el aviso de productos no disponibles:
  se ofrece, pero no se vende

#### Scenario: Opción con stock

- **GIVEN** un Kiosko con el ajuste activo y un combo con una opción
  almacenable con stock en la ubicación de origen
- **WHEN** el Kiosko carga sus datos
- **THEN** la opción llega disponible

#### Scenario: Opción sin stock con el ajuste apagado

- **GIVEN** un Kiosko sin el ajuste y un combo con una opción almacenable sin
  stock
- **WHEN** el Kiosko carga sus datos
- **THEN** la opción llega disponible y sale en la cuadrícula, como en el
  Kiosko nativo

### Requirement: Stock tomado al cargar la página del Kiosko

El Kiosko SHALL filtrar con el stock leído al cargar la página; no guarda
caché en el navegador, así que recargar la página o abrir la sesión SHALL
tomar el stock y el ajuste actuales. Con la página abierta el filtro SHALL
quedar como se cargó.

#### Scenario: Recargar la página toma el stock actual

- **GIVEN** un Kiosko con el ajuste activo que no ofrece un almacenable sin
  stock
- **WHEN** se repone el stock en la ubicación de origen y se recarga la página
  del Kiosko
- **THEN** el producto aparece

#### Scenario: Producto que se agota con el Kiosko abierto

- **GIVEN** un Kiosko abierto que ofrece un almacenable con una unidad
- **WHEN** se vende la última unidad
- **THEN** el producto sigue visible hasta recargar la página o abrir la sesión

#### Scenario: Producto marcado disponible con el Kiosko abierto

- **GIVEN** un Kiosko abierto con el ajuste activo
- **WHEN** un gerente marca "Disponible en autopedido" a un almacenable sin
  stock
- **THEN** el aviso `PRODUCT_CHANGED` del core lo agrega al Kiosko hasta
  recargar la página

#### Scenario: Cambiar el ajuste con el Kiosko abierto

- **GIVEN** un Kiosko abierto
- **WHEN** se activa o apaga el ajuste en la compañía
- **THEN** el Kiosko lo aplica al recargar la página: es un campo de la
  compañía y no avisa al Kiosko como un cambio de la caja
