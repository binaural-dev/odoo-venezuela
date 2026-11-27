## 0. Preparación

- [x] 0.1 Code review (2026-11-13): el aviso de la caja tras una Z impresa sin
      sincronizar invitaba a repetir la Z
- [x] 0.2 Decisión del usuario (2026-11-13): sin cambios para la Z sin papel
      (comportamiento normal de la máquina)

## 1. Implementación

- [x] 1.1 `ClosePosPopup._printFiscalReportZ`: "Reporte Z impreso con
      advertencia" cuando falla Odoo después de la Z

## 2. Pruebas

- [x] 2.1 Hoot de la caja: Odoo falla tras la Z; S1 que lanza un error
- [x] 2.2 Hoot del Kiosko: S1 que lanza un error

## 3. Cierre

- [x] 3.1 OpenSpec validado (`--strict`) y archivado en el mismo PR
