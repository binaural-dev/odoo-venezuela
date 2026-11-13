## ADDED Requirements

### Requirement: Reporte Z obligatorio con el S1 leído antes de la Z

El Reporte Z desde el popup de cierre DEBE (MUST) exigir un driver conectado y la confirmación del cajero, y leer el S1 ANTES de `printReportZ()`, como el flujo IoT. Sin `registeredMachineNumber` o sin un `dailyClosureCounter` entero NO DEBE (MUST NOT) imprimir la Z. Con la Z impresa DEBE (MUST) sincronizar `account.move.report_z` y `pos.session.set_report_z` con ese contador (el de la última Z; ellos le suman 1) y solo entonces invocar el cierre nativo (`confirm()`).

#### Scenario: Cierre completo

- **WHEN** el cajero confirma el Reporte Z, la lectura del S1 y la impresión son exitosas
- **THEN** se sincronizan `account.move.report_z` y `pos.session.set_report_z` con el contador leído antes de la Z y luego se ejecuta el cierre nativo de la sesión

#### Scenario: La sesión guarda la Z impresa

- **GIVEN** una máquina cuya última Z es la 0146 (el S1 devuelve 146)
- **WHEN** el cajero cierra con Z y la máquina imprime la 0147
- **THEN** la sesión queda con `report_z = 147`

#### Scenario: Confirmación rechazada

- **WHEN** el cajero cancela la confirmación del Reporte Z
- **THEN** no se envía ningún comando y la sesión no se cierra

#### Scenario: S1 ilegible antes de la Z

- **WHEN** el S1 no devuelve serial o contador válidos
- **THEN** se avisa que no se imprimió el Reporte Z, la máquina no recibe la Z y la sesión no se cierra

#### Scenario: La Z no se imprime

- **WHEN** el comando de la Z falla
- **THEN** se avisa del error y no se sincroniza Odoo ni se cierra la sesión

## MODIFIED Requirements

### Requirement: Reporte Z de la sesión del PdV

`pos.session` DEBE (MUST) guardar los datos de su Reporte Z: `report_z`, `serial_machine` (campo propio, ya no relacionado con la caja) y `report_z_date`. `set_report_z(values)` DEBE (MUST) escribir `report_z = _dailyClosureCounter + 1`, `serial_machine = _registeredMachineNumber` y la fecha y hora actuales, sin tocar `pos.config.serial_machine`. Con el S1 leído antes de la Z, `report_z` es la Z impresa, sin ceros a la izquierda. `report_z` y `serial_machine` siguen cargados en el PdV.

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

## REMOVED Requirements

### Requirement: Reporte Z obligatorio y sincronización con Odoo

**Reason**: leía el S1 después de imprimir la Z y la sesión quedaba con una Z de más (HKA80: Z 0147 impresa, `report_z = 148`); si el S1 fallaba, la Z ya había salido sin sincronizar y un segundo intento imprimía otra.

**Migration**: lo reemplaza "Reporte Z obligatorio con el S1 leído antes de la Z". Sin cambios de datos: las sesiones ya cerradas conservan su `report_z`.
