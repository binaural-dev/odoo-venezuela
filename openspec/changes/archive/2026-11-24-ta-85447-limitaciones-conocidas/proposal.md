## Why

Revisión del PR binaural-dev/odoo-venezuela#1572 (tarea
https://www.binauraldev.com/odoo/project/614/tasks/85447). Dos observaciones quedaron como
decisión del autor (2026-11-24) y no como cambio de código:

1. **La puerta del PdV depende solo de la cola local** (SaulOrte, 19/11, punto 3). Si se pierde
   la cola del navegador (almacenamiento borrado, otro navegador u otra PC), la venta siguiente
   se imprime sin verificar el pedido anterior.
2. **Falla sin foto después de un pago** (pastor-binaural, 13/11). Si la máquina no está en
   reposo al empezar o S1 no responde, no hay foto: una falla después de un pago devuelve el
   resultado de siempre y el pedido queda pendiente, y se puede reimprimir.

## What Changes

Solo documentación: las dos quedan escritas en las specs como limitación conocida y riesgo
aceptado.

- **Cola local perdida:** no duplica. El pedido sigue marcado en el servidor, no se reimprime, y
  el asistente y la resolución del PdV rechazan un número que ya es de otro documento. Lo que
  pasa es que ese pedido queda para revisión manual. Volver a llenar la cola desde el servidor
  tendría su propio riesgo: una entrada vieja, verificada después de otro documento, ve el
  contador +1 y se le atribuiría ese número. Queda como mejora aparte avisar al cajero, al cargar
  el PdV, de los pedidos marcados de la caja que no están en la cola.
- **Falla sin foto:** no es una regresión (antes cualquier falla quedaba igual), y sin foto no hay
  contra qué verificar. Queda como riesgo aceptado.

## Impact

- `openspec/specs/l10n_ve_pos_mf` y `openspec/specs/l10n_ve_mf_base`: un escenario cada una.
- Sin cambios de código.
