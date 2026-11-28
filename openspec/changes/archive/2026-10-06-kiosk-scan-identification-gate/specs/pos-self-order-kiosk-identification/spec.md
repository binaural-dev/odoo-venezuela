# Spec delta: pos-self-order-kiosk-identification

## ADDED Requirements

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
