# Diseño: código de divisa con IGTF y resultado verificado de la máquina fiscal

## 1. Lo que se midió en la máquina de pruebas

HKA80 Z7C7046254, modo fiscal, Flag 21 = 00, Flag 50 = 00, 2026-10-31. Comandos crudos por
el puerto serie y el driver real en Chrome. S1 en formato largo de 16 campos: [1] subtotal de
ventas, [2] última factura, [3] facturas del día, [6] última NC, [11] contador Z.

| Prueba | Resultado |
|---|---|
| Factura exenta 1,00: `iR*`, `iS*`, ítem, `3`, `101`, `199` | Tras `101` ACK sigue abierta (0x61); el `199` ACK la cierra. Número +1, subtotal +1,00 |
| `199` con la máquina en reposo | NAK, nada cambia: **ACK del `199` = documento cerrado** |
| Ítem y `7` sin pagos | "FACTURA ANULADA": número +1, facturas del día +1, **subtotal sin cambio** |
| Ítem, `3`, pago parcial `201`, foto con el documento abierto | S1 ya cuenta la factura (número y subtotal): **comprometida desde el primer pago** |
| … y luego `7` | ACK, 0x60, subtotal igual: el `7` **no la anula, la termina válida** (manual: "no se anulará sino que continuará en totalizar") |
| Factura con IVA 16% de base 1,00 | Subtotal +1,00: acumula la **base sin IVA** |
| NC contra la 505 | NC +1; el subtotal de ventas no cambia |
| NC con ítem y `7` | NC +1 (anulada); acumulado de NC (`U0X`) sin cambio |
| Reinicio con documento abierto sin pagos | Al prender la anula sola: número +1, subtotal igual |
| Reinicio con un pago registrado | No anula: queda válida |
| Código 20 con Flag 50 = 00 | La máquina **acepta** `220…` y **rechaza** el `199` (3 NAK); el documento queda abierto y comprometido |
| Después de un `7` | ~1 s en 0x61 mientras imprime |
| Al reiniciar | Chrome pierde el puerto USB hasta reconectar |

Conclusión: con la foto de S1 antes de abrir el documento, número y subtotal dicen qué
pasó **sin importar qué comando lo terminó**: número +1 y subtotal mayor = válida; número +1 y
subtotal igual = anulada; número igual = nada.

## 2. Código fiscal de divisa (backend y PdV)

- `pos.payment.method._check_foreign_currency_fiscal_code_igtf`: `@api.constrains` con un
  callable (`odoo/orm/models.py`, `_constraint_methods`) que solo declara los campos que
  existen; sin `l10n_ve_pos_igtf` ningún método puede tener 20-24. El código se lee como
  `TfhkaDriver._isDivisaPaymentMethod` (solo dígitos: `"2"` es el `02`).
- `get_data_invoice` corta al principio si un pago (monto distinto de cero, con el signo del
  documento) usa un método 20-24 sin `apply_igtf` (`_mfFindForeignCodeWithoutIgtfPayment`).
  Cubre la venta y la impresión de pendientes; un vuelto o un pago en cero no cuentan.

## 3. Driver: resultado verificado (`l10n_ve_mf_base`)

```text
printInvoice / printCreditNote / printDebitNote
 └─ _printWithOutcome(docType, print)
      ├─ _readDocumentSnapshot: ENQ en reposo + S1 (una sola vez) → { number, salesSubtotal, Z, serial }
      │    (sin reposo o sin S1 → sin foto → resultado de siempre)
      ├─ print()  ← cuerpo de siempre (_printInvoiceDocument, …), sin cambios
      │    _sendDocumentCommand anota paymentSent (2XX/1XX) y closeAcked (ACK del 199)
      ├─ éxito → se devuelve tal cual
      ├─ error sin ningún pago enviado → printed: false (no se consulta nada más)
      └─ error con pagos → _documentOutcome: estado (reintenta solo si no responde); si quedó
                 abierto, hasta 4 consultas por si imprime una anulada y luego "7"; S1 → comparar
```

| S1 después vs foto | Factura | NC / ND |
|---|---|---|
| sin ningún pago enviado (`2XX…`, `1XX`, `199`) | no impresa | no impresa |
| número igual | no impresa; desconocido si el `199` se aceptó | igual |
| +1 y subtotal mayor | **impresa** (`recovered`) | — |
| +1 y subtotal igual | anulada → no impresa; desconocido si el `199` se aceptó | — |
| +1 (sin subtotal) | — | impresa si hubo ACK del `199`; si no, desconocido |
| +2 o más | desconocido (`unattributable`) | igual |
| otro serial (se mira antes que el número) | desconocido (`other_printer`) | igual |
| S1 sin el contador del documento | desconocido (`unattributable`): revisión manual, no frena | igual |
| estado o S1 sin respuesta | desconocido (`no_response`) | igual |
| Z distinto (solo en verificaciones tardías) | se ignora el subtotal; el Z del resultado es el de la foto + 1 | igual |

Ante una contradicción se responde "desconocido": un "no impresa" equivocado lleva a reimprimir
(duplicado); un "desconocido" solo pide revisarlo.

- **El camino feliz no cambia:** mismos comandos más `ENQ`+`S1` al inicio, mismo resultado.
- **No se espera el reposo:** S1 se puede leer en cualquier estado y ya cuenta un documento
  comprometido; una anulada en curso puede dar N o N+1 sin subtotal, y las dos son "no
  impresa". Así no se demora la venta ni se pasa del tiempo de las pruebas.
- **`verifyDocument(verification)`** repite `_documentOutcome` con la foto guardada. Solo
  sirve si no se emitió otro documento en el medio (si el número avanzó 2, no concluye).
  Hace 3 consultas de estado (no 10): se llama antes de cada impresión mientras haya algo por
  verificar, y con la máquina muda no debe demorar cada venta.
- **Tiempos con la máquina muda:** cada consulta de estado sin respuesta tarda ~1 s, y cada
  lectura de S1 sin respuesta hasta 5 s (se reenvía una vez). Tras una falla con pagos enviados
  se agregan hasta ~10 s si la máquina no responde el estado, y hasta ~15 s si responde el
  estado pero no S1, antes de devolver `printed: null` (puede estar reiniciando). Cada
  verificación posterior: ~3 s con la máquina muda; hasta ~10 s si solo S1 no responde. Los
  reintentos de S1 se mantienen: sin ellos, una respuesta perdida deja el pedido por verificar
  en vez de recuperar su número.
- **`_readS1Data({ resend })`**: la foto previa no reintenta S1, para no demorar la venta.
- **`salesSubtotal`** se guarda como texto de dígitos (17 dígitos, más de lo que un Number
  representa) y se compara con BigInt; como texto se puede serializar.
- **Pagos enviados:** cuenta todo comando `2XX…` o `1XX` (ningún ítem, descuento, línea
  informativa ni `3` empieza así) y se marca antes de enviarlo.

## 4. PdV (`l10n_ve_pos_mf`)

- **La venta sigue:** en `finalizeValidation`, si `pushToMF` falla, se muestra el error y se
  sincroniza igual; la orden queda sin número ("Pendientes por facturar").
- **Por verificar:** si el driver devuelve `printed: null`, `pushToMF` guarda la
  verificación en `order.mf_print_verification` (campo Json de `pos.order`, se sincroniza) y
  en `PrintVerificationQueue` (localStorage).
- **Resolución antes de imprimir:** `PosStore._mfResolvePrintVerifications()` al inicio de
  `pushToMF` y de "Imprimir pedido pendiente", una a la vez (una segunda llamada espera la
  primera). Por cada entrada, `verifyDocument`:

  | Resultado | Pedido | Documento nuevo |
  |---|---|---|
  | `printed: true` | recibe el número (local y `mf_resolve_print_verification` por uuid) | se imprime |
  | `printed: false` | pendiente normal | se imprime |
  | `no_response` | sigue en la cola | **no se imprime**: queda pendiente (su impresión dejaría sin efecto la verificación) |
  | `other_printer` | sigue en la cola hasta que vuelva su máquina | se imprime |
  | `unattributable`, falla de la verificación, entrada dañada | sale de la cola, aviso, revisión manual | se imprime |

  Si el servidor no responde o el pedido aún no se sincronizó, la entrada guarda el resultado
  y se reintenta sin volver a verificar. Un error inesperado de la resolución no frena la venta.
- **Volver a validar:** si el servidor rechaza la sincronización (`RPCError`), el core deja la
  orden en borrador en la pantalla de pago. Al volver a validar, `pushToMF` resuelve la cola
  primero: si era esta orden y quedó impresa, recibe el número sin reimprimirse; si sigue por
  verificar, no se imprime.
- **Servidor:** `mf_set_print_verification` y `mf_resolve_print_verification` escriben con los
  permisos del usuario del PdV (sin `sudo()`), validan los datos (el número fiscal, solo
  dígitos) y la resolución solo cambia pedidos marcados.
- **La cola es por base de datos:** la clave de `localStorage` lleva `session.db`, para que
  varias bases en el mismo dominio no se mezclen.
- **"Imprimir pedido pendiente"** dice "Verificar impresión" en un pedido por verificar y no
  lo imprime; si su propia impresión queda desconocida, lo marca también en el servidor
  (`mf_set_print_verification`).
- **Resolución manual:** banner en el formulario del pedido y asistente
  `pos.order.mf.verification.wizard` (gerente del PdV) con número, serial y Z esperados.
  Un pedido sin número bloquea el cierre de sesión, así que siempre hay que resolverlo.

## 5. Detección previa

Antes de actualizar a un cliente, en su shell de Odoo:

```python
env.cr.execute("""
    SELECT id, COALESCE(name->>'es_VE', name->>'en_US') AS name, code_fiscal_printer, apply_igtf
    FROM pos_payment_method
    WHERE active
      AND regexp_replace(COALESCE(code_fiscal_printer, ''), '\\D', '', 'g') ~ '^[0-9]+$'
      AND regexp_replace(code_fiscal_printer, '\\D', '', 'g')::int BETWEEN 20 AND 24
      AND NOT COALESCE(apply_igtf, false)
    ORDER BY id""")
print(env.cr.fetchall())
```

Compara solo los dígitos, igual que la restricción y el driver (`' 20'` o `'20 '` también son
divisa). Si `apply_igtf` no existe, se quita esa condición.

**Si se escapó un método así:** todas sus ventas quedan pendientes por facturar. Con la sesión
abierta el método no se puede editar (core, `_is_write_forbidden`) y "Cerrar sesión e imprimir
Z" no deja cerrar con pedidos sin número. La salida:

1. un usuario con el grupo "Close POS session natively (skip mandatory Z report)"
   (`l10n_ve_pos_mf.group_pos_close_native`) cierra la sesión con "Cerrar sesión" (sin Z);
2. se corrige el método (código nacional 01-19 o "Aplica IGTF");
3. en la sesión siguiente, los pedidos se imprimen desde "Pendientes por facturar", que lista
   los pedidos de la caja y no solo los de la sesión, y esa sesión se cierra con su Z.

## 6. Alternativas descartadas

- **Volver fatal el `199`/`1XX`:** con Flag 50 = 00 y código 20 la factura queda comprometida
  por el pago y el `199` da NAK; hoy el driver devuelve el número correcto. Fatal = error con
  factura válida = duplicado.
- **"ACK del `7` = anulada":** falso después del primer pago (prueba 3).
- **Esperar el reposo antes de leer S1:** innecesario y, con el mock, pasaba del tiempo de
  Hoot.
- **`U0X` para distinguir NC anuladas:** funciona (medido) pero exige un protocolo de lectura
  en bloques nuevo; las NC se resuelven con el ACK del `199` y los pagos enviados.
- **Chequeo en `isOrderValid` / imprimir en `shouldHideValidationBehindFeedbackScreen`:**
  versiones anteriores de este cambio para no salir de la pantalla de pago; reemplazadas
  porque la venta no se debe detener.
- **Leer el Flag 50 / onchange de `apply_igtf`:** ver proposal.

## 7. Decisiones

- 2026-10-31: el change vive en `openspec/changes/` de la raíz (las specs de `l10n_ve_pos_mf`
  y `l10n_ve_mf_base` están en `openspec/specs/`), no en `l10n_ve_pos_mf/openspec/changes/`
  donde estaba el borrador.
- 2026-10-31: textos fuente en inglés con traducción es_VE.
- 2026-10-31 (usuario): corregir aquí que una falla de la máquina saque al cajero del pago;
  después, que la venta **siga** y la orden quede pendiente por facturar.
- 2026-10-31 (usuario): todo en este PR, incluido el driver, midiendo la regresión en la
  máquina de pruebas. "No es no tocar: es no causar errores".
- 2026-10-31 (usuario): una factura anulada impresa consume número (confirmado en la
  máquina).
- 2026-11-02 (usuario, tras el reviewer): aplicar las correcciones de la revisión. Lo
  principal sigue siendo que una falla de la máquina no saque la orden ni la deje en borrador:
  queda pendiente. No se aplica "exigir que el subtotal suba lo mismo que la base del
  documento": no se midió con IGTF ni con descuentos, y si el supuesto falla en otro modelo,
  facturas válidas quedarían por verificar.
- 2026-11-05 (usuario, tras la segunda revisión): **riesgo aceptado** en "Imprimir pedido
  pendiente". Ese botón imprime un pedido que ya está en el servidor y guarda el resultado con
  una llamada aparte. Si esa llamada falla (por ejemplo, sin red), el resultado queda solo en
  el navegador, y al recargar el pedido puede volver a pendientes y reimprimirse. Pasa cuando
  no se pudo marcar "por verificar" y también cuando falla el guardado del número tras una
  impresión exitosa (esto último ya pasaba antes de este cambio). Retener el pedido en la cola
  y bloquear su reimpresión frenaría la facturación: "prefiero asumir el riesgo de doble
  impresion y no parar la facturacion". Por el mismo criterio, un S1 sin el contador del
  documento va a revisión manual en vez de frenar las impresiones.
