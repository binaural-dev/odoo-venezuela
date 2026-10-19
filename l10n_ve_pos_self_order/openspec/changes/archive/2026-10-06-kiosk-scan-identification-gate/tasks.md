# Tasks

## 1. Frontend — desviar el escaneo sin cliente a identificación

- [x] 1.1 `self_order_router_service.js`: patch de `setup()` para guardar el
      `env` de Owl (acceso lazy a `env.services.self_order` sin dependencia
      circular)
- [x] 1.2 `self_order_router_service.js`: en `navigate()`, cuando `routeName`
      es `cart` y no es navegación explícita (`_allowScanCartNav`): mantener la
      rama `suppressScanCartNav` (solo escaneo/búsqueda) y, si no aplica,
      desviar a `identification` cuando el modo es `kiosk` y la orden actual no
      tiene `partner_id`
- [x] 1.3 `node --check` del archivo

## 2. Verificación manual (navegador) — PENDIENTE

- [ ] 2.1 PdV en modo Kiosko, sin identificar: escanear un producto en la
      pantalla inicial → **va a la pantalla de identificación** (no al carrito)
- [ ] 2.2 Identificarse por cédula → el producto escaneado sigue en la orden y
      aparece en `product_list`
- [ ] 2.3 Cliente ya identificado: escanear → va al carrito como siempre
- [ ] 2.4 Modo "solo escaneo/búsqueda" (`self_ordering_hide_catalog`): escanear
      tras identificarse sigue quedándose en la pantalla (no regresa a
      identificación)
- [ ] 2.5 Modo `mobile`/QR: sin cambios (el escaneo no desvía a identificación)

## 3. OpenSpec

- [x] 3.1 `openspec validate --changes kiosk-scan-identification-gate --strict`
      → válido
