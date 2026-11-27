## 0. Preparación

- [x] 0.1 Rama `19.0_feat-ta_85447_mf_foreign_code_and_verified_print` desde `origin/19.0`
      (`961726ad4`)
- [x] 0.2 El borrador estaba sin versionar en `l10n_ve_pos_mf/openspec/changes/` de otra
      instancia local; se escribe en la raíz (design.md → Decisiones)
- [x] 0.3 Mediciones en la máquina de pruebas HKA80 Z7C7046254 (design.md → 1), con el manual
      de protocolos V8.5.0

## 1. Implementación

- [x] 1.1 `l10n_ve_pos_mf`: restricción `_check_foreign_currency_fiscal_code_igtf` (callable),
      help de `code_fiscal_printer`, corte en `get_data_invoice`
- [x] 1.2 `l10n_ve_mf_base`: `printInvoice/CreditNote/DebitNote` → `_printWithOutcome`
      (cuerpos sin cambios, renombrados a `_print*Document`), `verifyDocument`,
      `salesSubtotal` en S1, `_readS1Data({ resend })`
- [x] 1.3 `l10n_ve_pos_mf`: la venta sigue si falla la impresión (`finalizeValidation`),
      `mf_print_verification`, `PrintVerificationQueue`, `_mfResolvePrintVerifications`,
      botón de pendientes, asistente de resolución manual con ACL para el gerente del PdV
- [x] 1.4 Traducciones es_VE; versiones 19.0.1.2.0 (`l10n_ve_mf_base`) y 19.0.3.2.0
      (`l10n_ve_pos_mf`)

## 2. Regresión del driver (máquina real)

Driver real en Chrome por Web Serial, PdV Caja 1 de `posconsultoria_85447` con `debug=assets`;
se envolvieron `connection.write/read` para registrar comandos, respuestas y tiempos. Mismos
pedidos con el driver de `origin/19.0` (A) y el nuevo (B).

- [x] 2.1 Camino feliz: factura exenta, IVA + exento, dos pagos, NC, código 20 con Flag 50 = 00
      y documento previo abierto → mismos campos, valores y comandos; solo se agrega
      `ENQ` + `S1` al inicio (+0,17 a +0,5 s; S1 ~70 ms, hasta ~400 ms si la máquina termina
      el ticket anterior)
- [x] 2.2 Fallas (A → B):
      - S1 falla tras el cierre: error → ✅ factura recuperada
      - pago registrado reportado fallido: error → ✅ factura recuperada (el `7` la totalizó)
      - ítem falla antes de pagar: error → `printed:false` (anulada)
      - falla el primer comando sin enviarlo: error → `printed:false`
      - NC falla antes de pagar: error → `printed:false`; NC con S1 fallido: error → ✅ recuperada
      - máquina muda tras el cierre: error → `printed:null`; `verifyDocument` → ✅
      - desconocida + otro documento antes de verificar → `verifyDocument` sigue `null`
- [x] 2.3 Reinicio real con el lapicero a mitad de una venta (Chrome pierde el USB):
      sin pagos → `printed:null`, al reconectar `verifyDocument` → `printed:false` (la máquina
      la anuló al prender); con un pago → `printed:null`, al reconectar → ✅ válida
- [x] 2.4 Repetición 2026-11-05 con el driver final (tras la primera revisión), misma máquina:
      - camino feliz: facturas 548-550 y NC 65, mismos campos, 3,4-4,3 s; `salesSubtotal`
        como texto y serializable
      - código 20 con Flag 50 = 00: 551 con el documento abierto, igual que antes; la 552 lo
        cierra con `7` (sin foto)
      - recuperadas: S1 falla tras el cierre (553), pago reportado fallido (554), NC con S1
        fallido (NC 67)
      - ítem falla antes de pagar: `printed:false` sin consultar S1 (555 anulada); primer
        comando sin enviar: `printed:false` (nada); NC antes de pagar: `printed:false` (NC 66
        anulada)
      - máquina muda tras el cierre: `printed:null` `no_response`; `verifyDocument` → 556;
        con otra factura (558) en el medio → `unattributable`; verificar con la máquina muda →
        `no_response` en 1,5 s
      - los ajustes de la segunda revisión (S1 sin el contador del documento, número fiscal
        solo con dígitos, cola por base de datos) se cubren con Hoot y Python, sin repetir en
        la máquina
- [ ] 2.5 Factura del backend (`l10n_ve_account_mf`) con el driver nuevo en la máquina real:
      ese módulo usa `printInvoice/printCreditNote/printDebitNote` (`mf_webserial_button.js`)
      y no está instalado en `posconsultoria_85447`. Queda para la tarea que revisa ese módulo

## 3. Pruebas automáticas

- [x] 3.1 Hoot `l10n_ve_mf_base` (`/web/tests?filter=%40l10n_ve_mf_base&debug=assets` en
      `posconsultoria_85447`, 2026-11-05): 55 pasan; 1 falla que ya fallaba en
      `origin/19.0` ("Conexión exitosa y lectura de status"). Las 30 existentes del driver
      pasan sin cambios salvo la de NC, que ahora ignora la lectura S1 previa
- [x] 3.2 Hoot `l10n_ve_pos_mf/unit` (`fiscal_payment_validation.test.js`, 2026-11-05): 22/22
- [x] 3.3 Python en base nueva (`~/docker-odoo`: `scripts/odoo-test <módulos> --container
      odoo-posconsultoria --addons /home/odoo/src/custom/posconsultoria/odoo-venezuela`,
      2026-11-05):
      - `l10n_ve_pos_mf` (lo que corre el CI): 27, 0 fallos; se omiten las 4 que
        necesitan `apply_igtf`
      - `l10n_ve_pos_mf,l10n_ve_pos_igtf`: 33, 0 fallos (también las de
        `l10n_ve_pos_igtf`; su `setUpClass` de migración se omite por falta de cuenta por
        cobrar, como en las corridas anteriores: ese módulo no se toca)
      - `l10n_ve_account_mf`: instala, sin tests Python
      - `l10n_ve_pos_mf_self_order`: error en `setUpClass` (`AccessError` de `l10n_ve_stock` al
        crear un producto); sale igual con `l10n_ve_pos_mf` y `l10n_ve_mf_base` de
        `origin/19.0`, no es de este cambio

## 4. PdV de punta a punta (máquina real, `finalizeValidation` y sincronización reales)

- [x] 4.1 Venta normal → factura 536 en el servidor
- [x] 4.2 Ítem falla antes de pagar → 537 anulada; pedido `done` sin número (pendiente)
- [x] 4.3 Máquina muda tras el cierre → pedido `done` por verificar; la venta siguiente lo
      resuelve primero (545) y luego imprime la suya (546)
- [x] 4.4 Resultado guardado sin servidor → al recargar se aplica sin volver a verificar
- [x] 4.5 Desconocida + documento por fuera → aviso de revisión manual; el asistente del
      backend la resuelve con 542 (número, serial y Z sugeridos)
- [x] 4.6 Repetición 2026-11-05 (tras la primera revisión): venta normal → 559; ítem falla
      antes de pagar → 560 anulada, pedido `done` pendiente con aviso; máquina muda tras el
      cierre → pedido `done` por verificar (561 válida); la venta siguiente lo resuelve con 561
      y luego imprime la suya (562)

## 5. Cierre

- [x] 5.1 Revisión con el reviewer de Binaural (dos rondas; correcciones aplicadas, menos el
      riesgo aceptado del 2026-11-05: ver design.md → Decisiones)
- [x] 5.2 Archivar el change y volcarlo en `openspec/specs/`
- [ ] 5.3 Despliegue: "Detección previa" (design.md) en cada cliente con máquina fiscal
