# Feature: barra de progreso de pasos en el Kiosko (l10n_ve_pos_self_order)

## Why

El flujo del Kiosko (autopedido) tiene varias pantallas encadenadas
(identificación por cédula → elegir productos → carrito → pago →
confirmación), pero el cliente no tiene una referencia visual de en qué punto
del proceso está ni cuántos pasos faltan. Una barra de progreso (stepper) fija
arriba mejora la orientación y reduce abandonos.

Alcance: modo **Kiosko** (`self_ordering_mode == 'kiosk'`). El flujo móvil/QR es
distinto y no lleva estos pasos.

## What Changes

Un componente **`KioskStepper`** fijo en la parte superior del Kiosko que
resalta el paso actual, derivándolo de la pantalla activa.

### Cómo detecta el paso (hallazgos técnicos — ya verificados)

El servicio `router` del self_order es **reactivo**
(`pos_self_order/app/services/self_order_router_service.js` →
`SelfOrderRouter extends Reactive`) y expone **`activeSlot`** (el nombre del slot
de la pantalla activa). Un componente que lea `useService("router").activeSlot`
se re-renderiza solo al navegar. Mapeo slot → paso:

| `activeSlot` | Paso |
|---|---|
| `identification` (slot añadido por este módulo) | **1 · Identificación** |
| `product_list` / `product` / `combo_selection` / `cart` | **2 · Productos** |
| `payment` | **3 · Pago** |
| `confirmation` | los 3 completados (✓) |
| `default` (bienvenida) | oculto |

### Dónde vive

- Módulo **`l10n_ve_pos_self_order`** (el paso 1 "Identificación" es propio de
  VE; el Kiosko genérico no lo tiene). Bundle `pos_self_order.assets`.
- Se **inyecta en la raíz `selfOrderIndex`** por t-inherit del template
  `pos_self_order.selfOrderIndex` (mismo patrón que
  `overrides/self_order_index.xml` de este módulo y el botón de debug de
  `l10n_ve_pos_mf_self_order`), gated por `selfOrder.kioskMode`.
- Usa el **color primario** del Kiosko (`config._self_ordering_style` →
  `primaryBgColor`/`primaryTextColor`, ver `insertKioskStyle` en
  `self_order_index.js`) para combinar con el tema de la caja.

### Comportamiento

- Barra sticky arriba, altura fija, sin tapar el contenido (empuja o se
  superpone con margen; cuidar no tapar el selector de idioma ni las categorías).
- Paso actual en color primario; pasos previos con ✓; siguientes atenuados.
- Oculto en la pantalla de bienvenida (`default`).
- En `confirmation`: los tres pasos completados (o se oculta — ver decisión
  abierta).

## Capabilities

### New Capabilities

- `pos-self-order-kiosk-progress-stepper`: el Kiosko muestra una barra de
  progreso de pasos (Identificación · Productos · Pago) que resalta el paso
  actual según la pantalla activa.

## Impact

- **Módulo**: `l10n_ve_pos_self_order` (componente nuevo + inyección en la raíz).
  Aditivo, no toca el flujo ni las pantallas existentes.
- **No toca** el core `pos_self_order` (solo t-inherit del template raíz).
- **Riesgo**: bajo. Puramente visual y aditivo.

## Decisiones abiertas (confirmar con el usuario al ejecutar)

1. **Etiqueta del paso 2:** el usuario mencionó "escanear", pero en el Kiosko se
   eligen productos tocando la pantalla. Opciones: "Productos" / "Elegir" /
   "Escanear" (si la caja tiene lector de barras). Default sugerido: "Productos".
2. **¿4º paso "Listo"?** en la confirmación, o basta con 3 pasos mostrados como
   completados. Default sugerido: 3 pasos, completados en confirmación.
3. **¿Solo Kiosko?** Default sugerido: sí (no mostrar en móvil/QR).

## Notas de implementación

- Ubicación sugerida: `static/src/app/kiosk_stepper/kiosk_stepper.{js,xml,scss}`
  + `static/src/overrides/self_order_index_stepper.xml` (t-inherit que lo monta).
  Nota: `l10n_ve_pos_mf_self_order` ya hace `t-inherit` de
  `pos_self_order.selfOrderIndex`; varios t-inherit del mismo template coexisten.
- Getter reactivo: `get step()` que lee `this.router.activeSlot` y devuelve
  1/2/3/"done"/null.
- Traducir etiquetas con `_t` (van al `.po`; este módulo usa español directo en
  strings de kiosko — seguir el estilo existente del módulo).

References: Tarea 78767 (Autopago POS V19),
https://binaural.odoo.com/odoo/action-341/78767
