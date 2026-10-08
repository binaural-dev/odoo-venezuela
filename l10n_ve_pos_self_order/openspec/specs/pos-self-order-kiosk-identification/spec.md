# pos-self-order-kiosk-identification Specification

## Purpose

Identificar al cliente por cédula/RIF antes de comprar en el Kiosko
(`pos_self_order` en modo `kiosk`): pantalla de identificación con teclado
numérico, búsqueda o creación del contacto en el servidor y gate que impide
llegar al catálogo o al carrito sin cliente identificado.

## Requirements
### Requirement: El Kiosko pide cédula antes de mostrar el catálogo

El sistema SHALL interceptar el inicio de un pedido en el Kiosko
(`self_ordering_mode == 'kiosk'`) para pedir la cédula del cliente antes de
navegar al catálogo de productos, cuando la orden actual no tiene ya un
`partner_id` asignado.

#### Scenario: Cliente nuevo en el Kiosko

- **GIVEN** una caja en modo Kiosko con `l10n_ve_pos_self_order` instalado
- **WHEN** el cliente pulsa "Empezar pedido" en la pantalla de bienvenida
- **THEN** se le muestra la pantalla de identificación (prefijo + cédula)
  antes de cualquier pantalla de catálogo o selección de ubicación

#### Scenario: Orden retomada con cliente ya identificado

- **GIVEN** una orden local (`selfOrder.currentOrder`) que ya tiene
  `partner_id` asignado (p. ej. tras recargar la página a mitad de compra)
- **WHEN** el flujo llega a `LandingPage.start()`
- **THEN** NO se vuelve a pedir la cédula — se navega directo a
  `"location"`/`"product_list"` como en el flujo nativo

#### Scenario: Modo Autopedido móvil (mobile) no se ve afectado

- **GIVEN** una caja en `self_ordering_mode == 'mobile'` (QR de mesa)
- **WHEN** un cliente escanea el QR e inicia su pedido
- **THEN** el flujo nativo de `LandingPage.start()` no cambia — la pantalla
  de identificación por cédula es exclusiva del modo Kiosko

### Requirement: Búsqueda de contacto por cédula reutiliza el domain existente

El sistema SHALL buscar un `res.partner` por cédula usando el mismo domain
que `res.partner.check_duplicate_vat` (`prefix_vat` + `vat`), sin
reimplementar la lógica de coincidencia. La respuesta de identificación y de
creación SHALL incluir, además de `id`/`name`/`phone`, la cédula que el propio
cliente tecleó (`vat`/`prefix_vat`) — no es información nueva para él.

#### Scenario: Cédula ya registrada

- **GIVEN** un `res.partner` existente con `prefix_vat='V'`, `vat='12345678'`
- **WHEN** el cliente teclea esa combinación en la pantalla de
  identificación del Kiosko
- **THEN** el servidor lo encuentra y devuelve `id`, `name`, `phone`, `vat` y
  `prefix_vat`, y el cliente pasa directo al catálogo con ese `partner_id`
  asignado a la orden

#### Scenario: Cédula no registrada

- **GIVEN** ninguna combinación `prefix_vat`+`vat` coincidente
- **WHEN** el cliente teclea una cédula nueva
- **THEN** el servidor responde "no encontrado" y el cliente ve el
  formulario de creación (nombre, apellido, teléfono) sin perder la cédula
  ya tecleada

#### Scenario: El endpoint de creación devuelve la cédula tecleada

- **GIVEN** un contacto recién creado desde el Kiosko
- **WHEN** el servidor responde al cliente tras la creación
- **THEN** la respuesta expone los mismos campos que la búsqueda (`id`,
  `name`, `phone`, `vat`, `prefix_vat`)

### Requirement: Creación de contacto desde el Kiosko reutiliza los defaults de dirección de la compañía

El sistema SHALL crear el `res.partner` nuevo con las mismas direcciones
por defecto que ya usa el formulario reducido de la caja normal
(`res.partner.default_get` bajo el flag de contexto
`l10n_ve_pos_partner_defaults`), sin duplicar esa lógica.

#### Scenario: Creación de contacto nuevo desde el Kiosko

- **GIVEN** un cliente que completó nombre, apellido, teléfono y cédula en
  la pantalla de identificación del Kiosko (cédula no encontrada)
- **WHEN** el servidor procesa la creación
- **THEN** el `res.partner` se crea con `name` = nombre + apellido
  concatenados, `phone`, `prefix_vat`/`vat` de la cédula tecleada, y
  `country_id`/`state_id`/`city_id`/`municipality`/`parish_id`/`zip`
  precargados desde `env.company.partner_id` — el mismo resultado que
  produciría abrir el formulario reducido de la caja normal con esos datos

#### Scenario: El endpoint de creación no filtra información privada distinta a la búsqueda

- **GIVEN** un contacto recién creado desde el Kiosko
- **WHEN** el servidor responde al cliente tras la creación
- **THEN** la respuesta expone los mismos campos públicos que la búsqueda
  (id, name, phone) — mismo criterio que ya sigue `validate_partner`

### Requirement: La cédula identificada queda disponible en el cliente del Kiosko

El sistema SHALL exponer `vat`/`prefix_vat` del partner al cliente del Kiosko
también en la carga self-data de `res.partner`
(`_load_pos_self_data_read`), no solo en la respuesta de identificación, para
que sobrevivan a re-sincronizaciones del partner y las integraciones de pago
(p. ej. Megasoft, `binaural_megasoft_self_order`) las reusen desde
`order.partner_id` sin volver a pedirlas.

#### Scenario: Una integración de pago lee la cédula del partner de la orden

- **GIVEN** un pedido del Kiosko cuyo cliente ya se identificó por cédula
- **WHEN** una integración de pago (Megasoft) necesita la cédula para su
  transacción
- **THEN** la lee de `order.partner_id.vat` en el cliente, sin abrir un popup
  ni un segundo flujo de identificación

#### Scenario: La cédula sobrevive a una re-sincronización del partner

- **GIVEN** un partner identificado presente en los modelos del cliente
- **WHEN** el kiosko vuelve a leer ese `res.partner` por la vía self-data
  (p. ej. al sincronizar la orden con el servidor)
- **THEN** el registro conserva `vat`/`prefix_vat`, porque
  `_load_pos_self_data_read` los inyecta en cada lectura

### Requirement: Teclado numérico en pantalla para la cédula/RIF

La pantalla de identificación del Kiosko SHALL ofrecer un teclado numérico en
pantalla (grid 3×4: dígitos 1-9, retroceso, 0 y limpiar) debajo del campo de
cédula/RIF, para que el cliente pueda introducir la cédula sin teclado físico.
El campo SHALL seguir siendo editable por teclado físico o del sistema.

#### Scenario: Introducir dígitos con el numpad

- **GIVEN** la pantalla de identificación del Kiosko en el paso de cédula
- **WHEN** el cliente pulsa una tecla de dígito del teclado en pantalla
- **THEN** el dígito se añade al final de la cédula (`state.vat`) y se limpia
  cualquier mensaje de error visible

#### Scenario: Retroceso y limpiar

- **GIVEN** una cédula parcialmente tecleada con el numpad
- **WHEN** el cliente pulsa retroceso (⌫)
- **THEN** se elimina el último carácter de la cédula
- **WHEN** el cliente pulsa limpiar (C)
- **THEN** la cédula queda vacía

#### Scenario: El teclado físico sigue disponible

- **GIVEN** un Kiosko con teclado físico o del sistema operativo
- **WHEN** el cliente escribe la cédula directamente en el campo
- **THEN** el valor se acepta igual que con el numpad — el teclado en pantalla
  es aditivo, no exclusivo

### Requirement: Acción primaria en la barra inferior

La acción primaria de la pantalla de identificación SHALL vivir en el pie de
página, alineada a la derecha, a la misma altura que el botón "Atrás" (alineado
a la izquierda). La acción primaria SHALL conmutar su etiqueta y su handler
según el paso: "Continue" (`onIdentify`) en el paso `identify` y "Create and
continue" (`onCreate`) en el paso `create`. NO SHALL existir un botón de acción
primaria de ancho completo en el área central.

#### Scenario: Paso de identificación

- **GIVEN** la pantalla en el paso `identify`
- **WHEN** se renderiza el pie de página
- **THEN** muestra "Atrás" a la izquierda y "Continue" a la derecha; al pulsar
  "Continue" se ejecuta `onIdentify()`

#### Scenario: Paso de nuevo cliente

- **GIVEN** una cédula no encontrada que llevó al paso `create`
- **WHEN** se renderiza el pie de página
- **THEN** muestra "Atrás" a la izquierda y "Create and continue" a la derecha;
  al pulsar el botón se ejecuta `onCreate()`

### Requirement: Escanear en la pantalla inicial sin cliente lleva a identificación

El sistema SHALL desviar a la pantalla de identificación cualquier navegación
automática al carrito (`cart`) disparada por un escaneo cuando el modo es `kiosk`
y la orden actual no tiene `partner_id`, en lugar de dejarla llegar al carrito.
El producto recién escaneado SHALL permanecer en la orden y quedar visible tras
identificarse. Esta puerta SHALL respetar la navegación explícita al carrito
(botón de pago) dejándola pasar, y SHALL aplicar solo en modo Kiosko (no en
`mobile`/QR).

#### Scenario: Escanear antes de identificarse

- **GIVEN** una caja en modo Kiosko con `l10n_ve_pos_self_order` instalado y una
  orden sin `partner_id` (p. ej. en la pantalla de bienvenida)
- **WHEN** el cliente escanea un producto disponible con el lector
- **THEN** se muestra la pantalla de identificación (prefijo + cédula) en lugar
  del carrito, y el producto escaneado queda en la orden

#### Scenario: El producto escaneado sobrevive a la identificación

- **GIVEN** un producto escaneado que llevó a la pantalla de identificación
- **WHEN** el cliente completa la identificación por cédula
- **THEN** navega a la lista de productos (o a la selección de ubicación si hay
  presets) con el `partner_id` asignado y el producto escaneado presente en la
  orden

#### Scenario: Escanear con cliente ya identificado

- **GIVEN** una orden en el Kiosko que ya tiene `partner_id` asignado
- **WHEN** el cliente escanea otro producto disponible
- **THEN** el producto se añade y se navega al carrito como en el flujo nativo
  (no se vuelve a la identificación)

#### Scenario: Modo "solo escaneo / búsqueda" conserva su comportamiento

- **GIVEN** un Kiosko con `self_ordering_hide_catalog` activo y el cliente ya
  identificado en la pantalla de escaneo/búsqueda
- **WHEN** el cliente escanea un producto
- **THEN** permanece en la pantalla de escaneo/búsqueda (no se desvía a la
  identificación ni salta al carrito)

#### Scenario: Modo móvil/QR no se ve afectado

- **GIVEN** una caja en `self_ordering_mode == 'mobile'`
- **WHEN** un cliente escanea un producto
- **THEN** el flujo nativo no cambia — el desvío a identificación es exclusivo
  del modo Kiosko

