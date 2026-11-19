## 1. Implementación

- [x] 1.1 `isOrderValid` frena la divisa sin IGTF con la máquina conectada
- [x] 1.2 `check_print_out_invoice/refund` rechazan el documento de un pedido por verificar
- [x] 1.3 Asistente: solo dígitos y número libre por máquina y tipo de documento
- [x] 1.4 Mensaje en el chatter al resolver (PdV y asistente)
- [x] 1.5 Aviso ante un error inesperado en `pushToMF`
- [x] 1.6 Filtro "Impresión fiscal por verificar" en los pedidos
- [x] 1.7 `verifyDocument` valida su entrada
- [x] 1.8 Texto fuente en inglés en `PrintPendingOrderButton.xml`
- [x] 1.9 Versiones y traducciones es_VE
- [x] 1.10 Gancho `_mfOrderGoesToFiscalPrinter` (y el PR del puente en integra-addons)
- [x] 1.11 Asistente: serial de la foto y número mayor que el de la foto
- [x] 1.12 NC/ND abierta después del `7`: `document_open` sin comparar S1, con aviso de reiniciar
- [x] 1.13 Chatter con el número que el pedido conserva
- [x] 1.14 `MockSerialConnection._saveDeviceInfo`
- [x] 1.15 `verifyDocument` valida `closeAcked` y `docType`; chatter con número conservado y "no emitido"

## 2. Pruebas

- [x] 2.1 Python (`l10n_ve_pos_mf`): asistente con el número de otro pedido (con ceros), de
      otra máquina, de una NC y de una factura del backend; solo dígitos; chatter (también
      con el usuario del PdV); filtro; impresión desde Contabilidad bloqueada
- [x] 2.2 Hoot (`l10n_ve_pos_mf`): `isOrderValid` y `validateOrder` no imprimen ni sincronizan;
      con IGTF o sin máquina sigue; error inesperado avisado
- [x] 2.3 Hoot (`l10n_ve_mf_base`): factura con pago anulada y sin número; NC con pago (+1 y
      mismo número); NC y factura abiertas después del `7`; ND con S1 de 16 campos; S1 mudo al
      empezar; verificación dañada
- [x] 2.4 Python: serial y número imposibles en el asistente; número conservado en el chatter;
      autor del mensaje con el usuario del PdV; filtro sin los resueltos

## 3. Cierre

- [x] 3.1 Revisión con el reviewer de Binaural, dos rondas (aprobar con cambios menores; aplicados)
- [x] 3.2 Archivar el change y volcarlo en `openspec/specs/`
