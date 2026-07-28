## Context

El PdV de Odoo 19 trata una línea de cantidad negativa como una forma
válida de devolución rápida dentro de una orden de venta. En Venezuela no
lo es: esa orden se factura como venta con cantidad negativa y así llega a
la impresora fiscal (`l10n_ve_pos_mf`) y al Libro de Ventas, en vez de
emitirse como nota de crédito. El flujo correcto (`TicketScreen` → orden
original → `Refund`) ya existe y debe seguir intacto.

La dificultad no es detectar el signo, sino **acertar con el conjunto de
exenciones**: el core produce cantidades negativas legítimas por al menos
tres caminos distintos, dos de ellos ignorando el valor de retorno de
`setQuantity`, de modo que un guard mal colocado los rompe en silencio en
vez de dar error.

Restricciones de partida:

- `l10n_ve_pos` es un override de `point_of_sale`; no se puede tocar el
  core ni asumir que el usuario tiene módulos fiscales de otros países.
- El fichero `static/src/overrides/models/pos_order_line.js` ya existe y
  está dedicado a los importes en moneda extranjera, con supuestos propios
  sobre `parseFloat` y redondeo.
- Una `ValidationError` durante el sync del PdV deja la orden atascada en
  el navegador: cualquier regla de servidor tiene que ser demostrablemente
  más estricta que el frontend, nunca al revés.

## Goals / Non-Goals

**Goals:**

- Impedir que una línea de una orden de venta quede con cantidad negativa,
  por cualquier vía de la interfaz del PdV.
- Preservar sin cambios los flujos de reembolso y devolución nativos.
- Que la regla quede realmente impuesta, no solo sugerida por la interfaz.
- Mensaje de error claro y con la misma UX que los avisos nativos del
  numpad.

**Non-Goals:**

- Precios unitarios y descuentos negativos (`numpadMode === "price"` /
  `"discount"`): fuera del alcance pedido.
- Sanear las órdenes negativas ya existentes en base de datos.
- Cambiar cómo se contabiliza o factura un reembolso.

## Decisions

### Interceptar en `PosOrderline.setQuantity`, no en el numpad

`OrderSummary.updateSelectedOrderline` es el sitio obvio (ahí vive la tecla
`+/-`), pero solo cubre el numpad. Los demás caminos que fijan cantidad —
`QuantityButtons`, código de barras con peso (`PosOrderline.setup` →
`setQuantity(code.value)`), `setQuantityByLot`, y la propagación a líneas
hijas de combo dentro del propio `setQuantity` — lo esquivarían.
`setQuantity` es el cuello de botella por el que pasan todos.

*Alternativa descartada:* validar al sincronizar/pagar. Detecta el problema
demasiado tarde, cuando el cajero ya cobró, y no le dice qué línea corregir.

### Reutilizar el contrato `{title, body}` en vez de abrir un diálogo

En Odoo 19 `setQuantity` devuelve `true`, o un objeto `{title, body}` que
`OrderSummary._setValue` renderiza como `AlertDialog` y seguido resetea el
`number_buffer`. Es el mismo mecanismo del mensaje nativo "Positive
quantity not allowed". Devolver ese objeto da UX idéntica a la del core sin
componentes nuevos, sin importar `dialog` en el modelo y sin duplicar el
reseteo del buffer.

*Alternativa descartada:* inyectar el servicio `dialog` en el `PosOrderline`
y lanzar el diálogo desde ahí. Rompe la separación modelo/componente y
dejaría el `number_buffer` sucio.

### Las exenciones son tres, y la del preset es obligatoria

1. `refunded_orderline_id` — línea de reembolso real.
2. `order_id.is_refund` (solo servidor) — cubre líneas que el core añade a
   una orden de reembolso sin vincularlas, p. ej. el descuento global de
   `pos_discount`, que copia `qty: baseLine.quantity` y por tanto nace
   negativo sobre un reembolso.
3. `order_id.preset_id.is_return` — preset nativo "Return mode".

La tercera no es opcional: `PosOrder.setPreset` y `PosStore.addLineToOrder`
fuerzan cantidad negativa **ignorando el valor de retorno** de
`setQuantity`. Bloquear ahí no produce error visible, solo deja el carrito
en positivo — un fallo silencioso, que es peor que el problema original.

*Alternativa descartada para el servidor:* exentar también cualquier orden
que tenga alguna línea con `refunded_orderline_id`. Protegería frente a que
`is_refund` no persistiera en el sync, pero abre un agujero real (una orden
que mezcle venta y reembolso quedaría exenta entera). Se descarta porque
`is_refund` es un campo almacenado del que ya depende la contabilidad
nativa (`sign = -1 if order.is_refund else 1`), así que su persistencia
está garantizada.

### Doble guard: frontend para la UX, servidor para la regla

El guard de JS es la primera línea: mensaje claro, sin romper la sesión. No
impone nada por sí solo — el sync del PdV y el backend escriben `qty` por
RPC. La `@api.constrains` es lo que convierte esto en una regla. Se
comparan las cantidades con `float_compare` a la precisión decimal
`Product Unit` para que el ruido de redondeo no dispare la validación.

### Importar `parseFloat` con alias

El fichero destino ya usa el `parseFloat` **global** sobre cadenas de
`toFixed()` (siempre con punto decimal) para los importes en moneda
extranjera. El `parseFloat` de `@web/views/fields/parsers` que usa el core
en `setQuantity` es sensible al locale y en es_VE espera coma decimal:
importarlo con su nombre sombrearía al global y rompería el cálculo de
precios. Se importa como `parseFloatLocale` y se envuelve en `try/catch`
para que una entrada no parseable delegue en el core y falle igual que en
Odoo estándar, en vez de convertir un error de formato en un bloqueo por
signo.

## Risks / Trade-offs

- **Una orden legítima con línea negativa fuera de las tres exenciones
  bloquearía el sync y dejaría la orden atascada en el navegador** → Se
  auditaron todos los caminos que generan `qty` negativo en
  `point_of_sale`, `enterprise` y `odoo-venezuela`: solo existen
  `_prepare_refund_data`, `onDoRefund` y el preset `is_return`, los tres
  exentos. `l10n_ve_pos_igtf` únicamente toca pagos y `l10n_ve_pos_mf` ya
  normaliza con `Math.abs(...)` antes de enviar a la impresora fiscal.

- **`OrderSummary.handleDecreaseLine` crea a propósito una línea negativa
  para reducir una línea ya enviada, y quedaría bloqueada** → Ese camino
  solo se alcanza con `pos.disallowLineQuantityChange()` verdadero, que en
  este stack siempre es `false`; solo lo sobreescriben `l10n_de_pos_res_cert`,
  `l10n_se_pos` y `pos_blackbox_be`, ninguno instalado en VE. Si alguna vez
  se instalara uno, habría que exentar ese flujo explícitamente.

- **Las órdenes negativas históricas quedan como están** → Aceptado.
  `@api.constrains` solo se evalúa en `create`/`write` de los campos
  vigilados, así que el upgrade del módulo no falla; sí fallaría reescribir
  su `qty` desde el backend, que es el comportamiento deseado.

- **La regla cubre la cantidad, no el importe** → Un descuento o un precio
  unitario negativo siguen siendo posibles desde el numpad y producen el
  mismo efecto contable indeseado. Queda documentado como trabajo aparte.

## Migration Plan

1. Desplegar el código y actualizar el módulo: `-u l10n_ve_pos`. Necesario
   para la `@api.constrains` y para las traducciones nuevas; solo recargar
   assets activa el guard de JS pero deja el mensaje en inglés.
2. Verificar en navegador el checklist de `tasks.md` §4, en particular que
   el reembolso completo sigue creando líneas negativas y sincronizando.
3. **Rollback**: revertir el commit y volver a actualizar el módulo. No hay
   migración de datos ni cambios de esquema, así que el rollback es
   inmediato y no deja residuo.

## Open Questions

- ¿Hay alguna configuración de PdV en producción usando presets con
  "Return mode"? Si no se usa ninguno, la exención 3 es solo defensiva; si
  se usa, entra en el checklist de verificación (`tasks.md` §4.8).
- ¿Se quiere extender la misma regla a descuentos y precios unitarios
  negativos? De quererse, es un change aparte sobre la misma capability.
