# Spec delta: pos-self-order-kiosk-fiscal-print

## ADDED Requirements

### Requirement: El Kiosko libera el puerto serial tras cada impresión fiscal

El sistema SHALL liberar (desconectar) el puerto Web Serial de la máquina
fiscal inmediatamente después de cada impresión o reimpresión puntual
(`printKioskFiscalInvoice`, `reprintKioskFiscalCopy`), tanto si la operación
tuvo éxito como si falló, dado que el Kiosko es desatendido y no ofrece un
control de cara al cliente para desconectarla manualmente.

#### Scenario: Impresión exitosa libera el puerto

- **GIVEN** el Kiosko conectado a la máquina fiscal e imprimiendo la factura
  de una orden recién registrada
- **WHEN** `printKioskFiscalInvoice` termina con éxito
- **THEN** el puerto queda cerrado (`TfhkaDriver.isConnected === false`) y
  disponible para otro consumidor (otra caja, el panel Fiscalizador del
  backoffice)

#### Scenario: Impresión fallida también libera el puerto

- **GIVEN** el Kiosko conectado a la máquina fiscal, y la impresión falla
  (NAK, timeout, o error del driver)
- **WHEN** `printKioskFiscalInvoice` resuelve con `valid: false`
- **THEN** el puerto igualmente se cierra — el fallo no deja la conexión
  colgada

#### Scenario: La siguiente impresión reconecta sola

- **GIVEN** el puerto ya fue autorizado una vez (pareo previo) y quedó
  liberado tras la transacción anterior
- **WHEN** llega una nueva orden a imprimir
- **THEN** `ensureFiscalPrinterConnected` reabre el puerto vía `autoConnect()`
  sin requerir gesto del usuario

#### Scenario: El pareo manual (modo debug) también libera el puerto

- **GIVEN** un técnico pareando el puerto desde el modo debug
  (`pairFiscalPrinter`)
- **WHEN** la verificación de pareo (conectar + `getStatus`) termina
- **THEN** el puerto se libera igual que tras una impresión — la
  autorización del puerto (lo que permite reconectar sin prompt) no depende
  de mantenerlo abierto

### Requirement: El arranque del Kiosko no reserva el puerto serial

El sistema SHALL verificar, al arrancar la app del Kiosko, únicamente si el
puerto de la máquina fiscal sigue PAREADO (autorizado en una sesión anterior),
sin abrirlo — la apertura real del puerto ocurre solo bajo demanda, en cada
impresión/reimpresión/pareo puntual.

#### Scenario: El arranque no compite por el puerto con otro consumidor

- **GIVEN** el Kiosko recién cargado, con el puerto de la máquina fiscal ya
  autorizado en una sesión anterior
- **WHEN** `SelfOrder.setup()` se ejecuta
- **THEN** se consulta la lista de puertos autorizados
  (`navigator.serial.getPorts()`) sin llamar a `port.open()`, de modo que
  otra pestaña (backoffice, otra caja) puede tomar el puerto en cualquier
  momento mientras el Kiosko está inactivo

#### Scenario: Sin pareo previo, el arranque solo lo señala

- **GIVEN** el Kiosko recién cargado, sin ningún puerto autorizado todavía
- **WHEN** `SelfOrder.setup()` se ejecuta
- **THEN** se deja un aviso (consola) de que falta parear desde el menú
  Debug, sin intentar abrir ni solicitar permiso de puerto

### Requirement: El panel Debug prueba la conexión bajo demanda, no un flag en memoria

El sistema SHALL ofrecer, en el panel Debug del Kiosko, una acción que
verifique la conexión real con la máquina fiscal (conectar, consultar estado,
liberar) en vez de depender de un flag `isConnected` en memoria que, con el
modelo bajo demanda, es `false` la mayor parte del tiempo en reposo.

#### Scenario: "Comprobar estado de conexión" prueba el hardware

- **GIVEN** el panel Debug del Kiosko abierto, con la máquina fiscal pareada
  pero sin ninguna operación en curso
- **WHEN** el técnico pulsa "Comprobar estado de conexión"
- **THEN** el sistema conecta, consulta el estado de la impresora, libera el
  puerto, y muestra el resultado real (conectada / desconectada) — no un
  flag desactualizado

#### Scenario: El badge de estado no asume "desconectada" antes de la primera prueba

- **GIVEN** el panel Debug recién abierto, sin que se haya ejecutado todavía
  ninguna prueba de conexión ni pareo en esta sesión del panel
- **WHEN** se renderiza el badge de estado
- **THEN** se muestra un estado neutro ("sin comprobar"), no "desconectada"
