# Tasks

## 1. Diseño (confirmar al ejecutar)

- [ ] 1.1 Confirmar etiqueta del paso 2 ("Productos" / "Elegir" / "Escanear").
- [ ] 1.2 Confirmar si va un 4º paso "Listo" o 3 pasos + completado en
      confirmación.
- [ ] 1.3 Confirmar solo-kiosko (no móvil).

## 2. Componente

- [ ] 2.1 `static/src/app/kiosk_stepper/kiosk_stepper.js`: componente OWL que lee
      `useService("router").activeSlot` (reactivo) y expone `get step()` con el
      mapeo slot→paso (ver proposal). Gated a `selfOrder.kioskMode`.
- [ ] 2.2 `kiosk_stepper.xml`: barra sticky arriba, 3 pasos (círculo + etiqueta),
      paso actual resaltado (color primario), previos con ✓, siguientes
      atenuados. Oculto si `default` o no-kiosko.
- [ ] 2.3 `kiosk_stepper.scss`: estilos; usar variables del tema del kiosko o el
      color primario inyectado. No tapar selector de idioma ni categorías.

## 3. Montaje

- [ ] 3.1 `static/src/overrides/self_order_index_stepper.xml`: t-inherit de
      `pos_self_order.selfOrderIndex`, insertar `<KioskStepper/>` al inicio del
      contenedor (antes del `<Router/>`), con `t-if` de kiosko.
- [ ] 3.2 `static/src/overrides/self_order_index_stepper.js`: registrar el
      componente en `selfOrderIndex.components` vía `patch(selfOrderIndex, {...})`
      (mismo patrón que `overrides/self_order_index.js` para `IdentificationPage`).

## 4. Verificación manual (navegador)

- [ ] 4.1 Recorrer el flujo kiosko: el paso resaltado avanza
      Identificación→Productos→Pago según la pantalla.
- [ ] 4.2 Oculto en bienvenida; completado en confirmación.
- [ ] 4.3 No aparece en modo móvil/QR.
- [ ] 4.4 No tapa idioma ni categorías; combina con el color de la caja.

## 5. OpenSpec

- [ ] 5.1 `openspec change validate kiosk-flow-progress-stepper` → válido.
