## 0. Preparación

- [x] 0.1 Prueba del usuario con la HKA80 (2026-11-13): sin papel, sesión 88
      con 148 y Z 0149 impresa; sesión 89 con papel: 151, correcto
- [x] 0.2 Causa: `printReportZ()` reenviaba `I0Z` sin respuesta
      (`sendCommand`, 3 intentos)
- [x] 0.3 Code review y decisiones del usuario (2026-11-13): no reenviar la Z,
      distinguir la Z impresa sin sincronizar en la caja, probar S1 con error

## 1. Implementación

- [x] 1.1 `TfhkaDriver.printReportZ`: `resendOnNoResponse: false`; versión
      `19.0.1.1.4`
- [x] 1.2 Caja: S1 tras la Z sin confirmar (`_readPrintedReportZ`), aviso
      "Reporte Z sin confirmar" y "Reporte Z impreso con advertencia"
- [x] 1.3 Kiosko: lo mismo en `printKioskReportZ` y el panel de Debug

## 2. Pruebas

- [x] 2.1 Hoot `tfhka_driver.test.js`: Z sin respuesta sale una sola vez
- [x] 2.2 Hoot de la caja: S1 con error, Z sin confirmar con y sin avance del
      contador, Odoo falla tras la Z
- [x] 2.3 Hoot del Kiosko: S1 con error, Z sin confirmar con y sin avance, aviso
      del panel
- [ ] 2.4 Con la HKA80: sin papel durante la Z, sale una sola Z y la sesión no
      queda con otro número

## 3. Cierre

- [x] 3.1 OpenSpec validado (`--strict`) y archivado en el mismo PR
