## MODIFIED Requirements

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

#### Scenario: La máquina no confirma la Z pero la imprimió

- **GIVEN** la máquina sin papel, que no responde al `I0Z`
- **WHEN** el S1 leído después muestra el contador de Z avanzado
- **THEN** la caja sincroniza Odoo con la Z que salió y sigue con el cierre

#### Scenario: La máquina no confirma la Z

- **WHEN** la máquina no responde al `I0Z` y el S1 posterior no muestra el contador avanzado
- **THEN** se avisa "Reporte Z sin confirmar": revisar la máquina y no repetir la Z si salió; no se sincroniza ni se cierra la sesión

#### Scenario: Odoo falla después de imprimir la Z

- **WHEN** la Z salió y falla la sincronización con Odoo
- **THEN** se avisa que la Z se imprimió, que no se repita y que se cierre la sesión desde el backend
