# Spec delta: pos-self-order-kiosk-identification

## ADDED Requirements

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
reimplementar la lógica de coincidencia.

#### Scenario: Cédula ya registrada

- **GIVEN** un `res.partner` existente con `prefix_vat='V'`, `vat='12345678'`
- **WHEN** el cliente teclea esa combinación en la pantalla de
  identificación del Kiosko
- **THEN** el servidor lo encuentra y devuelve sus datos públicos (id, name,
  phone) sin exponer información privada adicional, y el cliente pasa
  directo al catálogo con ese `partner_id` asignado a la orden

#### Scenario: Cédula no registrada

- **GIVEN** ninguna combinación `prefix_vat`+`vat` coincidente
- **WHEN** el cliente teclea una cédula nueva
- **THEN** el servidor responde "no encontrado" y el cliente ve el
  formulario de creación (nombre, apellido, teléfono) sin perder la cédula
  ya tecleada

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
