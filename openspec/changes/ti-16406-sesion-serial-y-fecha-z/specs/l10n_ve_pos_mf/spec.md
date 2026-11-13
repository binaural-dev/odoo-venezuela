## MODIFIED Requirements

### Requirement: Reporte Z de la sesión del PdV

`pos.session` DEBE (MUST) guardar los datos del Reporte Z que cerró su día fiscal: `report_z`, `serial_machine` (campo propio de la sesión, ya no relacionado con la caja) y `report_z_date`. `set_report_z(values)` DEBE (MUST) escribir `report_z = _dailyClosureCounter + 1`, `serial_machine = _registeredMachineNumber` y la fecha y hora actuales, y DEBE (MUST) llenar `pos.config.serial_machine` cuando la caja no lo tiene, sin pisar uno existente. `report_z` y `serial_machine` siguen cargados en el PdV.

#### Scenario: Sincronización del Z en la sesión

- **WHEN** se llama a `set_report_z` con `_dailyClosureCounter = 41` y `_registeredMachineNumber = "Z7C0000001"`
- **THEN** la sesión queda con `report_z = 42`, `serial_machine = "Z7C0000001"` y la fecha y hora de la Z

#### Scenario: La caja sin serial lo toma de la Z

- **GIVEN** una caja con `serial_machine` vacío
- **WHEN** se registra la Z de una de sus sesiones
- **THEN** la caja queda con el serial de la máquina que imprimió la Z; si ya tenía uno, no cambia

#### Scenario: El serial queda en la sesión

- **GIVEN** una sesión que ya registró su Z con la máquina `Z7C0000001`
- **WHEN** se cambia el serial de la caja
- **THEN** la sesión sigue mostrando `Z7C0000001`
