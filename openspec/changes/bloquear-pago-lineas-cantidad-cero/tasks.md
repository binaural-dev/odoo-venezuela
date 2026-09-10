## 1. l10n_ve_pos — bloqueo del pago con líneas en 0

- [x] 1.1 Override de `PosStore.pay()` en `static/src/overrides/services/pos_store.js`
- [x] 1.2 Detectar líneas con `getQuantity() === 0` y listar sus nombres (`getFullProductName`)
- [x] 1.3 Mostrar `AlertDialog` con el mensaje "elimínalos o colócales la cantidad correcta" y abortar el paso a pago
- [x] 1.4 Pasar a `super.pay()` cuando no hay líneas en 0

## 2. Verificación

- [ ] 2.1 Probar en navegador: orden con una línea en cantidad 0 → al pulsar "Pago" aparece la alerta con el nombre del producto y NO cambia de pantalla
- [ ] 2.2 Corregir la cantidad (o eliminar la línea) → "Pago" pasa normalmente a la pantalla de pago
- [ ] 2.3 Orden sin líneas en 0 → "Pago" funciona sin regresión (incluye botón de pago móvil)
- [ ] 2.4 Línea con cantidad negativa (devolución) → no se bloquea
