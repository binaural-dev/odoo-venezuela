# Spec delta: pos-self-order-kiosk-endpoint-security

## ADDED Requirements

### Requirement: El panel de recuperación es una herramienta de administrador (token por-orden descartado)

El acceso a las rutas de recuperación SHALL controlarse con el **PIN de
supervisor** en el cliente (gate de Debug, `binaural_pos_hr_self_order`), NO con
un token por-orden. Esas rutas (`session_orders`, `create_invoice`,
`write_mf_invoice_data`) alimentan un **panel de administrador** cuyo propósito es
operar sobre CUALQUIER orden de la caja (recuperar/crear factura, reimprimir la
factura fiscal), y acotarlas por token por-orden rompería esa función. Se acepta el riesgo residual
de que quien lea el `access_token` del dispositivo pueda invocar estas rutas a
mano (mitigado por despliegue en red interna + los guards de esta spec). El
enforcement server-side se limita a lo que NO estorba al admin: tope de `limit`,
no-sobrescritura de correlativo fiscal, exposición mínima en las rutas de
identificación.

#### Scenario: El admin recupera/reimprime cualquier orden de la caja

- **GIVEN** un administrador que abrió el panel tras el PIN de supervisor
- **WHEN** selecciona una orden de la caja (de cualquier cliente/turno) para crear
  factura o reimprimir su copia fiscal
- **THEN** la operación procede (el panel no exige un token por-orden)

### Requirement: Las rutas públicas corren con `sudo` y hacen el enforcement en el controlador

Las rutas públicas del Kiosko SHALL correr con `sudo()` (el Kiosko puede abrirse
con un usuario deliberadamente restringido que solo ve el Kiosko y aun así debe
traer sus datos) y, por tanto, SHALL hacer el control de acceso
**explícitamente en el controlador** en vez de apoyarse en las record rules
— token por-orden con `consteq()` para toda acción sobre una orden concreta,
proyección mínima de campos, guards de estado, y rate-limit por `access_token` en
las rutas de identificación.

#### Scenario: Una ruta pública no da acceso a datos arbitrarios pese al `sudo`

- **GIVEN** una ruta pública que corre con `sudo()` (`res.partner`, `pos.order`)
- **WHEN** un llamante con solo el `access_token` del dispositivo pide un dato que
  no es suyo (una orden de otro cliente, o enumera cédulas)
- **THEN** el controlador lo rechaza o no lo expone por sí mismo (token por-orden
  ausente → rechazo; PII mínima → sin teléfono; rate-limit → sin barrido masivo),
  sin depender de que las record rules filtren

### Requirement: Exposición mínima de datos personales

Las rutas públicas del Kiosko SHALL exponer el mínimo de datos del `res.partner`.
El listado de recuperación (`session_orders`) NO SHALL incluir `vat`/`prefix_vat`
ni `phone` de los partners. La identificación (`identify`) NO SHALL devolver
`phone` (devuelve un flag `has_phone` en su lugar). El `vat` solo viaja donde es
imprescindible (la propia orden del cliente, para reimprimir su copia fiscal).

#### Scenario: Enumeración de cédulas no rinde PII

- **GIVEN** un llamante con el `access_token` del dispositivo que itera cédulas
  (secuenciales en VE) contra `identify`
- **WHEN** una cédula existe en `res.partner`
- **THEN** la respuesta no incluye teléfono (solo `id`/`name`/`vat`/`prefix_vat` +
  `has_phone`), y el rate-limit por `access_token` frena un barrido masivo. El
  nombre es inevitable (el Kiosko saluda por él), pero deja de ser un oráculo de
  teléfonos y el volumen queda acotado.

### Requirement: Completar el teléfono faltante no sobrescribe el existente

El Kiosko SHALL poder registrar el teléfono de un cliente existente que no lo
tenga (cuando `identify` devuelve `has_phone` falso) vía `set_phone`. Esa ruta
SHALL re-localizar al partner por su cédula/RIF (no por un `id` arbitrario) y
SHALL escribir el teléfono **solo si estaba vacío**, nunca sobrescribir uno ya
registrado. `identify_create` SHALL aplicar la misma regla fill-only cuando la
cédula ya existe.

#### Scenario: Cliente existente sin teléfono lo completa

- **GIVEN** un `res.partner` identificado por su cédula que no tiene `phone`
- **WHEN** el cliente teclea su teléfono y el Kiosko llama `set_phone`
- **THEN** se guarda el teléfono en ese partner y el flujo continúa

#### Scenario: No se puede pisar un teléfono ya registrado

- **GIVEN** un `res.partner` que ya tiene `phone`
- **WHEN** una llamada pública (`set_phone`/`identify_create`) envía otro teléfono
  para esa cédula
- **THEN** la ruta NO modifica el teléfono existente

### Requirement: Listados acotados

`session_orders` SHALL aplicar un tope superior duro al parámetro `limit`
(independiente del valor recibido) para impedir un scan grande desde una ruta
pública.

#### Scenario: limit excesivo se recorta

- **GIVEN** un llamante que pide `session_orders` con `limit` muy alto
- **WHEN** la ruta procesa la petición
- **THEN** el número de órdenes devueltas queda acotado por el tope duro

### Requirement: La creación de partner deduplica y valida formato

`identify_create` SHALL reusar la búsqueda de `identify` y devolver el partner
existente en vez de crear un duplicado cuando la cédula/RIF ya existe, y SHALL
validar el formato de cédula (V/E numérica) y RIF (J/G) antes de crear.

#### Scenario: Alta con una cédula ya existente

- **GIVEN** un `res.partner` que ya tiene esa `prefix_vat` + `vat`
- **WHEN** el Kiosko llama `identify_create` con la misma cédula
- **THEN** la ruta devuelve el partner existente y NO crea un duplicado

#### Scenario: Alta con formato inválido

- **GIVEN** una cédula/RIF con formato inválido
- **WHEN** el Kiosko llama `identify_create`
- **THEN** la ruta rechaza la creación con un error de validación

### Requirement: La persistencia del número fiscal no sobrescribe un correlativo ya emitido

`write_mf_invoice_data` (expuesto públicamente) SHALL rechazar la escritura si la
orden ya tiene `mf_invoice_number`, para no corromper correlativos fiscales SENIAT
ya emitidos. NO se comprueba el estado `posted` del `account.move`: escribir el
número fiscal sobre una factura contable ya posteada es el flujo normal en VE
(la factura se postea primero y el número de máquina fiscal se registra después),
así que ese guard rompería el caso legítimo. Un reintento legítimo tras un fallo
de escritura llega con `mf_invoice_number` aún vacío, de modo que el guard de
no-sobrescritura no lo bloquea.

#### Scenario: Reintento sobre una orden ya numerada

- **GIVEN** una orden del Kiosko que ya tiene `mf_invoice_number`
- **WHEN** se invoca `write_mf_invoice_data` de nuevo para esa orden
- **THEN** la ruta rechaza la operación sin modificar el número existente ni el
  `account.move`

#### Scenario: Primera escritura sobre una factura ya posteada

- **GIVEN** una orden del Kiosko facturada (su `account.move` está `posted`) que
  aún NO tiene `mf_invoice_number`
- **WHEN** se invoca `write_mf_invoice_data` con el número de máquina fiscal
- **THEN** la ruta acepta y persiste el número (flujo normal, no se bloquea por
  el estado `posted`)
