## 0. Preparación

- [x] 0.1 Revisado en la copia de Monfarmacia (2026-11-12): ninguna sesión tiene
      Reporte Z, el serial de la sesión es relacionado con la caja y nada llena
      el de la caja (CCCT C1–C3 cargados a mano por `admin` el 2026-10-28)
- [x] 0.2 Decisión del usuario (2026-11-12): guardar serial y fecha y hora de
      la Z en la sesión, en el PR del ticket 16406, para la caja y el Kiosko

## 1. Implementación

- [x] 1.1 `models/pos_session.py`: `serial_machine` propio, `report_z_date`, y
      `set_report_z` que los escribe y llena el serial de la caja si falta
- [x] 1.2 `views/pos_session.xml`: "Fecha del Reporte Z" junto a "Reporte Z"
- [x] 1.3 `i18n/es_VE.po` y versión `19.0.3.2.0`

## 2. Pruebas

- [x] 2.1 `tests/test_pos_session_report_z.py`: Z, serial y fecha en la sesión;
      serial de la caja vacío que se llena; serial existente que no se pisa;
      serial de la sesión que no cambia con la caja; cajero sin permisos sobre
      la caja. `odoo -u l10n_ve_pos_mf --test-tags /l10n_ve_pos_mf` en base
      nueva (2026-11-12, instancia `monfarmacia`): 8 tests, 0 fallos
- [x] 2.2 Kiosko real (base `monfarmacia_t16406`, máquina simulada): tras
      "Cerrar sesión e imprimir Z" la sesión quedó con Reporte Z 42, serial
      `Z7CE2E0001`, fecha y hora, y la caja con ese serial
- [ ] 2.3 Con la máquina de pruebas HKA80: confirmar si `report_z` es la Z
      impresa o la siguiente

## 3. Cierre

- [x] 3.1 Archivar el change y volcarlo en `openspec/specs/l10n_ve_pos_mf/spec.md`
