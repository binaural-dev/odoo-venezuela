# Diseño

## Por qué el hand-off pertenece a `l10n_ve_pos_mf` y no a `binaural_megasoft`

El puerto Web Serial de la máquina fiscal es un recurso propiedad del
módulo de la MF. `binaural_megasoft` es un canal de pago que casualmente
necesita ese mismo COM físico un instante; es un *consumidor*, no el
dueño. Tener el ciclo disconnect→reclaim dentro de megasoft significaba:

- Duplicar la lógica en cada integración externa que aparezca (Sitef,
  otro VPOS, etc.).
- Que un módulo que declara ser independiente de la MF manipulara sus
  internals (`window.fiscalPrinter.disconnect/connect`).

## Contrato del seam

`withFiscalPrinterReleased(criticalSection)` es el punto de acoplamiento:

- Inversión de dependencia: el dueño del recurso (MF) expone el mecanismo;
  el consumidor (megasoft) solo aporta la sección crítica.
- Feature-detection en el consumidor: `binaural_megasoft` sigue sin
  depender de `l10n_ve_pos_mf` en el manifest. Si el hook no existe, corre
  la sección directo. Así el mismo `binaural_megasoft` sirve para cajas
  con y sin máquina fiscal.
- `criticalSection` maneja sus propios errores/diálogos; el hook solo se
  ocupa del puerto. El resultado y las excepciones se propagan intactos.
- El `ui.block()`/`ui.unblock()` queda en el consumidor (es política de UX
  de megasoft: bloquear mientras el cajero interactúa con la app externa),
  pero como el reclamo ocurre dentro del hook y este se llama dentro del
  bloqueo, el overlay cubre todo el ciclo disconnect→externo→reclaim.

## Recuperación mid-sesión (FiscalPrinterButton)

`onMounted` solo corría una vez, así que una re-enumeración USB a media
sesión dejaba la MF muerta hasta un click. Los eventos
`navigator.serial` `connect`/`disconnect` son la señal correcta: el
navegador los emite cuando el dispositivo aparece/desaparece del bus
físico (no ante un `port.close()` de software). En `connect` reintentamos
`fp.connect()` (silencioso, filtra por identidad, así que un evento de
otro dispositivo no reconecta la MF por error). Los listeners se limpian
en `onWillUnmount` para no acumularse si el componente se re-monta.
