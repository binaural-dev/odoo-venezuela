## MODIFIED Requirements

### Requirement: Reporte Z de la sesión del PdV

`pos.session` DEBE (MUST) guardar los datos de su Reporte Z: `report_z`, `serial_machine` (campo propio, ya no relacionado con la caja) y `report_z_date`. `set_report_z(values)` DEBE (MUST) escribir `report_z = _dailyClosureCounter + 1`, `serial_machine = _registeredMachineNumber` y la fecha y hora actuales, sin tocar `pos.config.serial_machine`. `report_z` y `serial_machine` siguen cargados en el PdV.

#### Scenario: Sincronización del Z en la sesión

- **WHEN** se llama a `set_report_z` con `_dailyClosureCounter = 41` y `_registeredMachineNumber = "Z7C0000001"`
- **THEN** la sesión queda con `report_z = 42`, `serial_machine = "Z7C0000001"` y la fecha y hora de la Z

#### Scenario: El serial de la caja no cambia

- **GIVEN** una caja con o sin `serial_machine`
- **WHEN** se registra la Z de una de sus sesiones
- **THEN** el serial de la caja queda como estaba

#### Scenario: El serial queda en la sesión

- **GIVEN** una sesión que ya registró su Z con la máquina `Z7C0000001`
- **WHEN** se cambia el serial de la caja
- **THEN** la sesión sigue mostrando `Z7C0000001`
