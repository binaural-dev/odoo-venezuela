## 0. Decisión

- [x] 0.1 2026-11-06: el usuario aprueba la regla (pago justo → restante exacto; excedente → lo tecleado
      por la tasa; parcial sin cambios) y deja la alterna USD para después.

## 1. Implementación

- [x] 1.1 `setTenderAmount`: rama del pago justo y del excedente
- [x] 1.2 Comentario de `_getLocalDueBefore` en `l10n_ve_pos_igtf` (sin cambio de lógica)
- [x] 1.3 Revisión de Binaural (aprobar con cambios; el usuario aprueba todo): gancho
      `_getOverpaidTenderLocalAmount` sin red de seguridad, con override en `binaural_pos_multicurrency`
      para el cobro en Bs (integra-addons#3173); lo tecleado se redondea a la moneda de cobro; comentarios
      del signo de un negativo tecleado y de "medio céntimo de menos o de más". Sin cambio de versión.

## 2. Pruebas

- [x] 2.1 `payment_tender.test.js`: pagar de más en euros (10 € convertidos), el caso de la caja 1
      (18.560 Bs + € 25 → 25.123,91; € 18,47 → 18.560), lo tecleado redondeado (8,475 € → 8,48 €), el
      gancho del excedente y reembolsos con excedente a la tasa original
- [x] 2.2 Hoot en `pos_test_86066`: `l10n_ve_pos` con setTenderAmount 13/13 (131 en verde, con los 18
      fallos previos de descuentos y PartnerList); `binaural_pos_multicurrency` 25/25 (22 + 3 del cobro de
      más en Bs). IGTF no instalado en la base: no se corre su suite.
- [x] 2.3 PdV real, caja 78 de `pos_test_86066` (sesión 00131, tasas del 06-nov de `pos_consultor`):
      18.560 Bs con € 25 → línea 25.123,91 Bs, vuelto 6.563,91 Bs (órdenes 293 y 295); con € 18,47
      tecleados → 18.560 Bs exactos, sin vuelto (294 y 296); 8.500 Bs con € 8,475 → € 8,48 = 8.522,03 Bs
      (297)

## 3. Cierre

- [ ] 3.1 `openspec validate --strict` y archivar en el PR #1569
