# Feature: escanear en la pantalla inicial del Kiosko lleva a identificación

## Why

En modo Kiosko, el catálogo se pide solo tras identificar al cliente por cédula
(`LandingPage.start()` desvía a la pantalla de identificación cuando la orden no
tiene `partner_id`; ver capacidad `pos-self-order-kiosk-identification`). Pero el
**escaneo por lector es un listener global** de `pos_self_order/self_order_service`:
al escanear un producto —incluso estando en la pantalla inicial (bienvenida),
antes de identificarse— añade el producto y navega directo a `cart`, **saltándose
la puerta de identificación** que vive únicamente en `LandingPage.start()`.

Resultado: una orden llega al carrito/pago **sin cliente**, y como
`l10n_ve_pos` factura toda orden a un cliente real (SENIAT), la factura falla.
Es la misma clase de "bypass" ya diagnosticada para recargas en `/products` o
`/payment`, pero por la vía del escaneo en la pantalla inicial.

## What Changes

- **Frontend** (`SelfOrderRouter.navigate`, patch en
  `static/src/overrides/self_order_router_service.js`): en modo `kiosk`, cuando
  una navegación automática a `cart` (la que dispara el escaneo) ocurre y la
  orden actual **no tiene `partner_id`**, se desvía a la pantalla de
  `identification` en lugar de al carrito. El producto recién escaneado
  permanece en la orden y queda visible tras identificarse (la identificación
  navega a `product_list`/`location`).
- El override ya existente (que en modo "solo escaneo/búsqueda" se traga la
  navegación a `cart` vía `suppressScanCartNav`) se conserva: esa rama tiene
  prioridad. La navegación explícita al carrito (botón de pago,
  `_allowScanCartNav`) sigue pasando sin tocar.
- Para poder consultar el servicio `self_order` desde el router (que no puede
  declararlo como dependencia — `self_order` ya depende del router), se guarda
  el `env` de Owl en `setup()` y se lee `env.services.self_order` en
  `navigate()`.

## Capabilities

### Modified Capabilities

- `pos-self-order-kiosk-identification`: la puerta de identificación deja de
  poder saltarse escaneando un producto en la pantalla inicial; el escaneo sin
  cliente identificado lleva a la pantalla de identificación.

## Impact

- **Módulo**: `l10n_ve_pos_self_order`.
  - Frontend: `static/src/overrides/self_order_router_service.js` (bundle
    `pos_self_order.assets`).
- **No toca** el core `self_order_service` (el listener global de escaneo), ni
  controladores, ni RPC.
- **Compatibilidad**: en modo `mobile`/QR no aplica (gateado a `kiosk`). Con el
  cliente ya identificado, el escaneo sigue yendo al carrito como siempre.
- **Riesgo**: bajo. Aditivo y gateado por `self_ordering_mode === 'kiosk'` +
  ausencia de `partner_id`.

References: Tarea 78767 — Kiosko / Autopedido POS V19 (`pos_self_order`).
