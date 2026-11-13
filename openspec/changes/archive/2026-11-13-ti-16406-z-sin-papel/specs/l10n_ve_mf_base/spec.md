## MODIFIED Requirements

### Requirement: Reportes fiscales y gaveta

El driver DEBE (MUST) exponer `printReportX()` (comando `I0X`, consulta sin cerrar el día), `printReportZ()` (comando `I0Z`, cierre fiscal del día) y `openDrawer()` (comando `0`, apertura de gaveta), y en la fase de pagos enviar el comando `w` (abrir gaveta) cuando la orden trae `has_cashbox`. `printReportZ()` NO DEBE (MUST NOT) reenviar `I0Z` cuando la impresora no responde: devuelve `noResponse: true`, porque la Z pudo salir.

#### Scenario: Reporte Z

- **WHEN** se invoca `printReportZ()` con la impresora conectada y en reposo
- **THEN** se envía `I0Z` con timeout de reporte

#### Scenario: Reporte Z sin respuesta

- **GIVEN** una impresora que acepta el `I0Z` y no responde a tiempo (por ejemplo, sin papel)
- **WHEN** se invoca `printReportZ()`
- **THEN** el `I0Z` se envía una sola vez y el resultado es `success: false` con `noResponse: true`

#### Scenario: Orden con gaveta

- **WHEN** la orden trae `has_cashbox = true`
- **THEN** el comando `w` se envía antes de los comandos de pago
