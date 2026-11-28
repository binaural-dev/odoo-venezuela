# l10n_ve_pos_self_order

## Purpose

Ajusta el Kiosko/Autopedido nativo de Odoo (`pos_self_order`) a la localización venezolana: moneda alterna, identificación del cliente por cédula o RIF, facturación de cada orden y las reglas de seguridad de sus rutas públicas. Hasta 20 esta spec estaba repartida en una spec por funcionalidad dentro del módulo; cada sección de requisitos conserva el orden de esas funcionalidades:

- **pos-self-order-kiosk-address**: Pedir la dirección del cliente al crearlo desde el Kiosko (estado y municipio de Venezuela), opcional u obligatoria según `self_ordering_require_address`, con los catálogos de estados y municipios disponibles en el cliente.
- **pos-self-order-kiosk-available-products**: Llevar al autopedido (Kiosko y móvil) "Mostrar solamente los productos disponibles" (`pos_show_just_products_with_available_qty`, de `l10n_ve_pos`): no ofrece almacenables sin stock a mano en la ubicación de origen de la caja, la misma cantidad con la que filtra la caja (ticket 16064). El stock se toma al cargar la página del Kiosko.
- **pos-self-order-kiosk-cancel-popup**: Mostrar en español ("Sí"/"No") el popup de cancelar la orden del Kiosko, vía traducción `es_VE` del texto fuente del core.
- **pos-self-order-kiosk-endpoint-security**: Fijar las reglas de seguridad de las rutas públicas del Kiosko: corren con `sudo` y el controlador hace el enforcement (caja, token, alcance), exponen el mínimo de datos personales, acotan los listados y no sobrescriben datos ya existentes del contacto ni correlativos fiscales emitidos.
- **pos-self-order-kiosk-identification**: Identificar al cliente por cédula/RIF antes de comprar en el Kiosko (`pos_self_order` en modo `kiosk`): pantalla de identificación con teclado numérico, búsqueda o creación del contacto en el servidor y gate que impide llegar al catálogo o al carrito sin cliente identificado.
- **pos-self-order-kiosk-invoice-recovery**: Evitar que un rechazo de la facturación pierda una venta ya cobrada en el Kiosko: la orden se crea igual, la prueba del pago Megasoft queda persistida y las órdenes pendientes se facturan después desde el panel del Kiosko o desde el backend.
- **pos-self-order-kiosk-invoicing**: Garantizar que toda orden del Kiosko termine facturada al completarse el pago, de forma idempotente, ya que en Venezuela la venta al público desde el Kiosko exige factura.
- **pos-self-order-kiosk-keyboard**: Permitir al cliente escribir sus datos de contacto en el Kiosko con un teclado en pantalla, sin depender de un teclado físico.
- **pos-self-order-kiosk-orders-panel**: Ofrecer en el módulo base (sin depender de la máquina fiscal) el panel de órdenes del Kiosko y el shell de debug con un único punto de acceso, que los módulos dependientes (p. ej. el de máquina fiscal) extienden.
- **pos-self-order-kiosk-payment-summary**: Mostrar antes de pagar el desglose de montos de la orden del Kiosko (base imponible, impuestos por tasa y total en Bs. y en divisa).
- **pos-self-order-kiosk-phone-required**: Exigir y validar en el Kiosko un teléfono venezolano (operadora + 7 dígitos) al crear el contacto, en el cliente y en el servidor.
- **pos-self-order-kiosk-progress-stepper**: Mostrarle al cliente del Kiosko en qué paso del flujo de compra está (identificación, productos, pago) mediante una barra de progreso que solo aparece en modo `kiosk`.
- **pos-self-order-kiosk-required-fields-legend**: Indicar en los pasos de contacto del Kiosko qué campos son obligatorios con la leyenda "LOS CAMPOS MARCADOS CON * SON OBLIGATORIOS".
- **pos-self-order-kiosk-scan-search**: Permitir configurar por punto de venta un Kiosko de "solo escaneo / búsqueda" (`self_ordering_hide_catalog`): sin catálogo, con buscador, escaneo por lector siempre activo, resumen del pedido en la misma pantalla y pago directo sin pasar por el carrito.

## Requirements

### Requirement: Dirección opcional/obligatoria por configuración

El punto de venta SHALL exponer un ajuste booleano
`self_ordering_require_address` (Ajustes → sección de Autopedido/Kiosko,
visible solo en modo `kiosk`, mismo patrón que
`self_ordering_hide_catalog`). El paso de creación de contacto del Kiosko
SHALL ofrecer siempre Estado (`res.country.state`, restringido a Venezuela),
Municipio (`res.country.municipality`, filtrado por el estado elegido) y
Calle (texto libre). Con el ajuste desactivado estos campos SHALL ser
opcionales; con el ajuste activo SHALL ser obligatorios, tanto en cliente
como en servidor (`controllers/orders.py`, ruta `identify/create`).

El Municipio SHALL depender del Estado elegido: al cambiar el Estado, el
Municipio previamente elegido (si ya no pertenece al nuevo Estado) SHALL
limpiarse. El servidor SHALL validar que el Municipio recibido pertenezca al
Estado recibido, sin confiar en el pareo que mandó el cliente.

#### Scenario: Ajuste desactivado, dirección opcional

- **GIVEN** un Kiosko con `self_ordering_require_address` desactivado
- **WHEN** el cliente crea un contacto sin completar Estado/Municipio/Calle
- **THEN** el contacto se crea igualmente

#### Scenario: Ajuste activado, dirección obligatoria

- **GIVEN** un Kiosko con `self_ordering_require_address` activado
- **WHEN** el cliente intenta crear un contacto sin Estado, sin Municipio o
  sin Calle
- **THEN** se rechaza con un mensaje de error, tanto en cliente (al pulsar
  Crear se indica el campo que falta) como en servidor si se fuerza la llamada

#### Scenario: Municipio depende del Estado

- **GIVEN** el paso de creación de contacto con el desplegable de Municipio
- **WHEN** el cliente cambia el Estado elegido
- **THEN** el desplegable de Municipio se limpia y solo ofrece los
  municipios del nuevo Estado

#### Scenario: Servidor rechaza un pareo Estado/Municipio inconsistente

- **GIVEN** el ajuste `self_ordering_require_address` activado o desactivado
- **WHEN** llega una llamada a `identify/create` con un `municipality_id` que
  no pertenece al `state_id` recibido
- **THEN** el servidor rechaza la creación con un mensaje de error, sin
  confiar en el pareo que mandó el cliente

#### Scenario: Servidor rechaza un Estado que no es de Venezuela

- **GIVEN** el ajuste `self_ordering_require_address` activado o desactivado
- **WHEN** llega una llamada a `identify/create` con un `state_id` de otro
  país, o con un `municipality_id` sin `state_id`
- **THEN** el servidor rechaza la creación con un mensaje de error

#### Scenario: La dirección del cliente no se mezcla con la de la compañía

- **GIVEN** una compañía con dirección completa (estado, municipio, ciudad,
  parroquia y código postal)
- **WHEN** el cliente del Kiosko elige un estado (con o sin municipio)
- **THEN** el contacto se crea con el estado y municipio del cliente, y sin el
  municipio, la ciudad, la parroquia ni el código postal de la compañía
- **AND** si el cliente no manda dirección, el contacto conserva la dirección
  por defecto de la compañía

#### Scenario: Servidor rechaza textos demasiado largos

- **WHEN** llega un `name` o `street` de más de 255 caracteres
- **THEN** el servidor no crea el contacto y devuelve un mensaje de error

### Requirement: Datos de Estados/Municipios de Venezuela expuestos al Kiosko

El Kiosko SHALL recibir los `res.country.state` de Venezuela (ya expuestos
por el core `pos_self_order`) y los `res.country.municipality` de
`l10n_ve_location` (expuestos por este módulo vía
`pos.config._load_self_data_models` + `res.country.municipality` heredando
`pos.load.mixin`), con al menos `id`, `name`, `code`, `state_id` y
`country_id`.

#### Scenario: Municipios disponibles en el frontend del Kiosko

- **GIVEN** el Kiosko cargado
- **WHEN** el frontend consulta `this.selfOrder.models["res.country.municipality"]`
- **THEN** están disponibles los municipios de Venezuela con su(s)
  Estado(s) asociado(s)

### Requirement: El autopedido no carga almacenables sin stock con "Mostrar solamente los productos disponibles"

Con `pos_show_just_products_with_available_qty` activo en la compañía de la
caja, el autopedido (Kiosko y móvil) SHALL no cargar los productos
almacenables (`is_storable`) sin ninguna variante con stock a mano positivo en
la ubicación de origen del tipo de operación de la caja y sus hijas. Lo no
almacenable SHALL cargarse igual. Con el ajuste apagado la carga SHALL ser la
nativa.

#### Scenario: Almacenable sin stock

- **GIVEN** un Kiosko con el ajuste activo y un almacenable con stock a mano 0
  o negativo en su ubicación de origen
- **WHEN** el Kiosko carga sus datos
- **THEN** el producto y sus variantes no se cargan
- **AND** no sale en la cuadrícula ni en el buscador, y al escanearlo el Kiosko
  responde "No se encontró el producto"

#### Scenario: Stock en la ubicación de origen o sus hijas

- **GIVEN** un Kiosko con el ajuste activo y un almacenable con stock positivo
  en una ubicación hija de su ubicación de origen
- **WHEN** el Kiosko carga sus datos
- **THEN** el producto se carga

#### Scenario: Basta una variante con stock

- **GIVEN** un Kiosko con el ajuste activo y un almacenable con dos variantes,
  solo una con stock en la ubicación de origen
- **WHEN** el Kiosko carga sus datos
- **THEN** se cargan el producto y sus dos variantes

#### Scenario: Stock de otro almacén

- **GIVEN** un Kiosko con el ajuste activo y un almacenable con stock solo en
  otro almacén
- **WHEN** el Kiosko carga sus datos
- **THEN** el producto no se carga

#### Scenario: Lo no almacenable se carga sin stock

- **GIVEN** un Kiosko con el ajuste activo
- **WHEN** carga un servicio y un consumible sin control de stock, ambos sin
  stock
- **THEN** los dos se cargan

#### Scenario: Ajuste apagado

- **GIVEN** un Kiosko sin el ajuste
- **WHEN** carga sus datos
- **THEN** el almacenable sin stock se carga, como en el Kiosko nativo

#### Scenario: Carga real por la ruta pública

- **GIVEN** un Kiosko con el ajuste activo
- **WHEN** carga sus datos por la ruta pública, con el usuario por defecto del
  Kiosko y sin privilegios de superusuario
- **THEN** recibe el ajuste y los productos no almacenables, y no recibe el
  almacenable sin stock

### Requirement: Opciones de combo sin stock

Con el ajuste activo, una almacenable sin stock que el core carga como opción
de un combo SHALL llegar con `self_order_available = False`. El Kiosko SHALL no
mostrar en la cuadrícula (en ninguna categoría) ni en el buscador los
almacenables con `self_order_available = False`, SHALL no dejar elegirlos en el
combo y SHALL responder "no disponible" al escanearlos. El combo y sus
opciones con stock SHALL seguir disponibles.

#### Scenario: Opción sin stock

- **GIVEN** un Kiosko con el ajuste activo y un combo con una opción
  almacenable sin stock y otra con stock
- **WHEN** el cliente abre la cuadrícula y el combo
- **THEN** la opción sin stock no sale en la cuadrícula
- **AND** en el combo sale como "Agotado" y no se puede elegir, y la otra sí
- **AND** al escanearla el Kiosko responde "El producto no está disponible"

#### Scenario: Opción sin stock con categoría de PdV

- **GIVEN** un Kiosko con el ajuste activo y una opción de combo almacenable sin
  stock con una categoría de PdV
- **WHEN** el cliente abre esa categoría
- **THEN** la opción no sale
- **AND** una categoría de primer nivel que solo tenga opciones así no sale como
  pestaña
- **AND** una subcategoría así sigue en la barra de subcategorías y abre una
  cuadrícula vacía, como el Kiosko nativo con cualquier subcategoría vacía

#### Scenario: Almacenable desmarcado a mano para autopedido

- **GIVEN** un Kiosko con el ajuste activo y una opción de combo almacenable
  con stock a la que un gerente le quitó "Disponible en autopedido"
- **WHEN** el cliente abre la cuadrícula
- **THEN** la opción no sale (el Kiosko nativo la mostraría como "Agotado")

#### Scenario: Combo que no se puede completar

- **GIVEN** un Kiosko con el ajuste activo y un combo con una sola opción por
  grupo, almacenable y sin stock
- **WHEN** el cliente lo agrega
- **THEN** el Kiosko lo pasa directo al carrito sin la página del combo
- **AND** al pagar el core lo quita con el aviso de productos no disponibles:
  se ofrece, pero no se vende

#### Scenario: Opción con stock

- **GIVEN** un Kiosko con el ajuste activo y un combo con una opción
  almacenable con stock en la ubicación de origen
- **WHEN** el Kiosko carga sus datos
- **THEN** la opción llega disponible

#### Scenario: Opción sin stock con el ajuste apagado

- **GIVEN** un Kiosko sin el ajuste y un combo con una opción almacenable sin
  stock
- **WHEN** el Kiosko carga sus datos
- **THEN** la opción llega disponible y sale en la cuadrícula, como en el
  Kiosko nativo

### Requirement: Stock tomado al cargar la página del Kiosko

El Kiosko SHALL filtrar con el stock leído al cargar la página; no guarda
caché en el navegador, así que recargar la página o abrir la sesión SHALL
tomar el stock y el ajuste actuales. Con la página abierta el filtro SHALL
quedar como se cargó.

#### Scenario: Recargar la página toma el stock actual

- **GIVEN** un Kiosko con el ajuste activo que no ofrece un almacenable sin
  stock
- **WHEN** se repone el stock en la ubicación de origen y se recarga la página
  del Kiosko
- **THEN** el producto aparece

#### Scenario: Producto que se agota con el Kiosko abierto

- **GIVEN** un Kiosko abierto que ofrece un almacenable con una unidad
- **WHEN** se vende la última unidad
- **THEN** el producto sigue visible hasta recargar la página o abrir la sesión

#### Scenario: Producto marcado disponible con el Kiosko abierto

- **GIVEN** un Kiosko abierto con el ajuste activo
- **WHEN** un gerente marca "Disponible en autopedido" a un almacenable sin
  stock
- **THEN** el aviso `PRODUCT_CHANGED` del core lo agrega al Kiosko hasta
  recargar la página

#### Scenario: Cambiar el ajuste con el Kiosko abierto

- **GIVEN** un Kiosko abierto
- **WHEN** se activa o apaga el ajuste en la compañía
- **THEN** el Kiosko lo aplica al recargar la página: es un campo de la
  compañía y no avisa al Kiosko como un cambio de la caja

### Requirement: Popup de cancelar orden en español

El popup nativo de cancelar orden del Kiosko (`pos_self_order.CancelPopup`) SHALL mostrar el texto "¿Desea cancelar la orden?" y dos botones: "Sí" (confirma
la cancelación) y "No" (cierra el popup sin cancelar). La implementación SHALL
heredar el template del core (`t-inherit-mode="extension"`) sin reemplazarlo
por completo.

#### Scenario: Cliente abre el popup de cancelar

- **GIVEN** el cliente está en el carrito del Kiosko con al menos una línea
- **WHEN** toca "Cancelar orden"
- **THEN** ve el texto "¿Desea cancelar la orden?" con los botones "Sí" y "No"

#### Scenario: Confirmar cancelación

- **GIVEN** el popup de cancelar orden abierto
- **WHEN** el cliente toca "Sí"
- **THEN** la orden se cancela (mismo comportamiento que el core: `confirm()`)

#### Scenario: Descartar el popup

- **GIVEN** el popup de cancelar orden abierto
- **WHEN** el cliente toca "No"
- **THEN** el popup se cierra y la orden sigue intacta

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

### Requirement: El Kiosko pide cédula antes de mostrar el catálogo

El sistema SHALL interceptar el inicio de un pedido en el Kiosko
(`self_ordering_mode == 'kiosk'`) para pedir la cédula del cliente antes de
navegar al catálogo de productos, cuando la orden actual no tiene ya un
`partner_id` asignado.

#### Scenario: Cliente nuevo en el Kiosko

- **GIVEN** una caja en modo Kiosko con `l10n_ve_pos_self_order` instalado
- **WHEN** el cliente pulsa "Empezar pedido" en la pantalla de bienvenida
- **THEN** se le muestra la pantalla de identificación (prefijo + cédula)
  antes de cualquier pantalla de catálogo o selección de ubicación

#### Scenario: Orden retomada con cliente ya identificado

- **GIVEN** una orden local (`selfOrder.currentOrder`) que ya tiene
  `partner_id` asignado (p. ej. tras recargar la página a mitad de compra)
- **WHEN** el flujo llega a `LandingPage.start()`
- **THEN** NO se vuelve a pedir la cédula — se navega directo a
  `"location"`/`"product_list"` como en el flujo nativo

#### Scenario: Modo Autopedido móvil (mobile) no se ve afectado

- **GIVEN** una caja en `self_ordering_mode == 'mobile'` (QR de mesa)
- **WHEN** un cliente escanea el QR e inicia su pedido
- **THEN** el flujo nativo de `LandingPage.start()` no cambia — la pantalla
  de identificación por cédula es exclusiva del modo Kiosko

### Requirement: Búsqueda de contacto por cédula reutiliza el domain existente

El sistema SHALL buscar un `res.partner` por cédula con el mismo criterio de
coincidencia que `res.partner.check_duplicate_vat` (`prefix_vat` + `vat`),
entre los contactos que la caja puede facturar (ver "El Kiosko solo
identifica clientes que su caja puede facturar"). La respuesta de identificación y de
creación SHALL incluir, además de `id`/`name`/`phone`, la cédula que el propio
cliente tecleó (`vat`/`prefix_vat`) — no es información nueva para él.

#### Scenario: Cédula ya registrada

- **GIVEN** un `res.partner` existente con `prefix_vat='V'`, `vat='12345678'`
- **WHEN** el cliente teclea esa combinación en la pantalla de
  identificación del Kiosko
- **THEN** el servidor lo encuentra y devuelve `id`, `name`, `phone`, `vat` y
  `prefix_vat`, y el cliente pasa directo al catálogo con ese `partner_id`
  asignado a la orden

#### Scenario: Cédula no registrada

- **GIVEN** ninguna combinación `prefix_vat`+`vat` coincidente
- **WHEN** el cliente teclea una cédula nueva
- **THEN** el servidor responde "no encontrado" y el cliente ve el
  formulario de creación (nombre, apellido, teléfono) sin perder la cédula
  ya tecleada

#### Scenario: El endpoint de creación devuelve la cédula tecleada

- **GIVEN** un contacto recién creado desde el Kiosko
- **WHEN** el servidor responde al cliente tras la creación
- **THEN** la respuesta expone los mismos campos que la búsqueda (`id`,
  `name`, `phone`, `vat`, `prefix_vat`)

### Requirement: Creación de contacto desde el Kiosko reutiliza los defaults de dirección de la compañía

El sistema SHALL crear el `res.partner` nuevo con las mismas direcciones
por defecto que ya usa el formulario reducido de la caja normal
(`res.partner.default_get` bajo el flag de contexto
`l10n_ve_pos_partner_defaults`), sin duplicar esa lógica.

#### Scenario: Creación de contacto nuevo desde el Kiosko

- **GIVEN** un cliente que completó nombre, apellido, teléfono y cédula en
  la pantalla de identificación del Kiosko (cédula no encontrada)
- **WHEN** el servidor procesa la creación
- **THEN** el `res.partner` se crea con `name` = nombre + apellido
  concatenados, `phone`, `prefix_vat`/`vat` de la cédula tecleada, y
  `country_id`/`state_id`/`city_id`/`municipality`/`parish_id`/`zip`
  precargados desde `env.company.partner_id` — el mismo resultado que
  produciría abrir el formulario reducido de la caja normal con esos datos

#### Scenario: El endpoint de creación no filtra información privada distinta a la búsqueda

- **GIVEN** un contacto recién creado desde el Kiosko
- **WHEN** el servidor responde al cliente tras la creación
- **THEN** la respuesta expone los mismos campos públicos que la búsqueda
  (id, name, phone) — mismo criterio que ya sigue `validate_partner`

### Requirement: La cédula identificada queda disponible en el cliente del Kiosko

El sistema SHALL exponer `vat`/`prefix_vat` del partner al cliente del Kiosko
también en la carga self-data de `res.partner`
(`_load_pos_self_data_read`), no solo en la respuesta de identificación, para
que sobrevivan a re-sincronizaciones del partner y las integraciones de pago
(p. ej. Megasoft, `binaural_megasoft_self_order`) las reusen desde
`order.partner_id` sin volver a pedirlas.

#### Scenario: Una integración de pago lee la cédula del partner de la orden

- **GIVEN** un pedido del Kiosko cuyo cliente ya se identificó por cédula
- **WHEN** una integración de pago (Megasoft) necesita la cédula para su
  transacción
- **THEN** la lee de `order.partner_id.vat` en el cliente, sin abrir un popup
  ni un segundo flujo de identificación

#### Scenario: La cédula sobrevive a una re-sincronización del partner

- **GIVEN** un partner identificado presente en los modelos del cliente
- **WHEN** el kiosko vuelve a leer ese `res.partner` por la vía self-data
  (p. ej. al sincronizar la orden con el servidor)
- **THEN** el registro conserva `vat`/`prefix_vat`, porque
  `_load_pos_self_data_read` los inyecta en cada lectura

### Requirement: Teclado numérico en pantalla para la cédula/RIF

La pantalla de identificación del Kiosko SHALL ofrecer un teclado numérico en
pantalla (grid 3×4: dígitos 1-9, retroceso, 0 y limpiar) debajo del campo de
cédula/RIF, para que el cliente pueda introducir la cédula sin teclado físico.
El campo SHALL seguir siendo editable por teclado físico o del sistema.

#### Scenario: Introducir dígitos con el numpad

- **GIVEN** la pantalla de identificación del Kiosko en el paso de cédula
- **WHEN** el cliente pulsa una tecla de dígito del teclado en pantalla
- **THEN** el dígito se añade al final de la cédula (`state.vat`) y se limpia
  cualquier mensaje de error visible

#### Scenario: Retroceso y limpiar

- **GIVEN** una cédula parcialmente tecleada con el numpad
- **WHEN** el cliente pulsa retroceso (⌫)
- **THEN** se elimina el último carácter de la cédula
- **WHEN** el cliente pulsa limpiar (C)
- **THEN** la cédula queda vacía

#### Scenario: El teclado físico sigue disponible

- **GIVEN** un Kiosko con teclado físico o del sistema operativo
- **WHEN** el cliente escribe la cédula directamente en el campo
- **THEN** el valor se acepta igual que con el numpad — el teclado en pantalla
  es aditivo, no exclusivo

### Requirement: Acción primaria en la barra inferior

La acción primaria de la pantalla de identificación SHALL vivir en el pie de
página, alineada a la derecha, a la misma altura que el botón "Atrás" (alineado
a la izquierda). La acción primaria SHALL conmutar su etiqueta y su handler
según el paso: "Continue" (`onIdentify`) en el paso `identify` y "Create and
continue" (`onCreate`) en el paso `create`. NO SHALL existir un botón de acción
primaria de ancho completo en el área central.

#### Scenario: Paso de identificación

- **GIVEN** la pantalla en el paso `identify`
- **WHEN** se renderiza el pie de página
- **THEN** muestra "Atrás" a la izquierda y "Continue" a la derecha; al pulsar
  "Continue" se ejecuta `onIdentify()`

#### Scenario: Paso de nuevo cliente

- **GIVEN** una cédula no encontrada que llevó al paso `create`
- **WHEN** se renderiza el pie de página
- **THEN** muestra "Atrás" a la izquierda y "Create and continue" a la derecha;
  al pulsar el botón se ejecuta `onCreate()`

### Requirement: Escanear en la pantalla inicial sin cliente lleva a identificación

El sistema SHALL desviar a la pantalla de identificación cualquier navegación
automática al carrito (`cart`) disparada por un escaneo cuando el modo es `kiosk`
y la orden actual no tiene `partner_id`, en lugar de dejarla llegar al carrito.
El producto recién escaneado SHALL permanecer en la orden y quedar visible tras
identificarse. Esta puerta SHALL respetar la navegación explícita al carrito
(botón de pago) dejándola pasar, y SHALL aplicar solo en modo Kiosko (no en
`mobile`/QR).

#### Scenario: Escanear antes de identificarse

- **GIVEN** una caja en modo Kiosko con `l10n_ve_pos_self_order` instalado y una
  orden sin `partner_id` (p. ej. en la pantalla de bienvenida)
- **WHEN** el cliente escanea un producto disponible con el lector
- **THEN** se muestra la pantalla de identificación (prefijo + cédula) en lugar
  del carrito, y el producto escaneado queda en la orden

#### Scenario: El producto escaneado sobrevive a la identificación

- **GIVEN** un producto escaneado que llevó a la pantalla de identificación
- **WHEN** el cliente completa la identificación por cédula
- **THEN** navega a la lista de productos (o a la selección de ubicación si hay
  presets) con el `partner_id` asignado y el producto escaneado presente en la
  orden

#### Scenario: Escanear con cliente ya identificado

- **GIVEN** una orden en el Kiosko que ya tiene `partner_id` asignado
- **WHEN** el cliente escanea otro producto disponible
- **THEN** el producto se añade y se navega al carrito como en el flujo nativo
  (no se vuelve a la identificación)

#### Scenario: Modo "solo escaneo / búsqueda" conserva su comportamiento

- **GIVEN** un Kiosko con `self_ordering_hide_catalog` activo y el cliente ya
  identificado en la pantalla de escaneo/búsqueda
- **WHEN** el cliente escanea un producto
- **THEN** permanece en la pantalla de escaneo/búsqueda (no se desvía a la
  identificación ni salta al carrito)

#### Scenario: Modo móvil/QR no se ve afectado

- **GIVEN** una caja en `self_ordering_mode == 'mobile'`
- **WHEN** un cliente escanea un producto
- **THEN** el flujo nativo no cambia — el desvío a identificación es exclusivo
  del modo Kiosko

### Requirement: El cliente identificado queda en la orden que guarda el servidor

Las rutas `identify`, `identify/create` y `set_phone` SHALL devolver el `id`
del partner firmado (`pos.order._get_signed_self_partner_id` de la caja), la
única forma que el core de Odoo 19 acepta como `partner_id` de una orden del
Kiosko. Así, la orden sincronizada con `process-order` SHALL guardarse con ese
cliente y la orden local SHALL conservarlo con su cédula.

#### Scenario: Cliente existente identificado por cédula

- **GIVEN** un `res.partner` con `prefix_vat='V'` y `vat='12345678'`
- **WHEN** el cliente se identifica con esa cédula en el Kiosko
- **THEN** `identify` devuelve el partner con el `id` firmado, que
  `pos.order._get_self_partner_from_token` resuelve a ese partner

#### Scenario: Cliente creado o completado desde el Kiosko

- **GIVEN** una cédula no registrada, o un cliente registrado sin teléfono
- **WHEN** el Kiosko lo crea (`identify/create`) o le completa el teléfono
  (`set_phone`)
- **THEN** la respuesta trae el partner con el `id` firmado, también cuando
  `identify/create` devuelve un contacto que ya existía (dedup)

#### Scenario: La orden del Kiosko se guarda con el cliente identificado

- **GIVEN** un cliente identificado en el Kiosko y una orden con productos
- **WHEN** el Kiosko sincroniza la orden con `process-order`
- **THEN** la `pos.order` queda con el `partner_id` del cliente y la orden
  local conserva el partner con su cédula, así que una integración de pago
  (Megasoft) la lee de `order.partner_id.vat` sin bloquear el pago

#### Scenario: Un id sin firmar no asigna cliente

- **GIVEN** una orden del Kiosko cuyo `partner_id` es un id numérico
- **WHEN** el servidor arma la orden (`_check_pos_order`)
- **THEN** el core no asigna ningún cliente; por eso las rutas de
  identificación nunca devuelven el id sin firmar

### Requirement: El Kiosko solo identifica clientes que su caja puede facturar

La búsqueda por cédula de las rutas `identify`, `identify/create` y
`set_phone` SHALL considerar solo los `res.partner` que la factura de la caja
acepta: los de la compañía de la caja, los de sus compañías padre y los
compartidos (`res.partner._check_company_domain(pos_config.company_id)`, la
misma regla con la que `account.move` valida el cliente). Un contacto de otra
empresa de la base SHALL tratarse como no encontrado.

#### Scenario: Cédula registrada solo en otra empresa

- **GIVEN** un `res.partner` con `prefix_vat='V'` y `vat='12345678'` de una
  empresa que no es la de la caja ni una de sus matrices
- **WHEN** el cliente se identifica con esa cédula en el Kiosko
- **THEN** `identify` no devuelve ese contacto y el Kiosko le pide registrarse;
  `set_phone` tampoco le completa el teléfono

#### Scenario: Cédula registrada en dos empresas

- **GIVEN** la misma cédula en un contacto de otra empresa (con el `id` más
  bajo) y en un contacto de la empresa de la caja
- **WHEN** el cliente se identifica con esa cédula
- **THEN** `identify` devuelve el contacto de la empresa de la caja

#### Scenario: Kiosko de una sucursal

- **GIVEN** un Kiosko cuya caja es de una sucursal y un cliente de la empresa
  matriz
- **WHEN** el cliente se identifica con su cédula
- **THEN** `identify` devuelve ese contacto, que la factura de la sucursal
  acepta

### Requirement: El cliente nuevo del Kiosko se crea en la empresa raíz de la caja

`identify/create` SHALL crear el `res.partner` nuevo con `company_id` = la
compañía raíz de la caja (`pos_config.company_id.root_id`), para que todas las
cajas de la empresa puedan facturarle. Si la creación la rechaza una validación
(p. ej. el control global de cédula duplicada de `l10n_ve_contact`), la ruta
SHALL responder con ese mensaje en `error` y sin contacto, en vez de un error de
servidor.

#### Scenario: Registro desde el Kiosko de una sucursal

- **GIVEN** un Kiosko de una sucursal, con el control de cédula duplicada por
  compañía, y una cédula registrada solo en otra empresa
- **WHEN** el cliente se registra en el Kiosko
- **THEN** se crea un contacto nuevo en la empresa matriz, el de la otra
  empresa no cambia y la siguiente identificación lo encuentra

#### Scenario: Control global de cédula duplicada

- **GIVEN** el control de cédula duplicada global de `l10n_ve_contact` y una
  cédula registrada solo en otra empresa
- **WHEN** el cliente intenta registrarse en el Kiosko
- **THEN** la respuesta trae `error` con el mensaje de la validación, sin
  contacto, y no se crea un duplicado

### Requirement: La orden del Kiosko se crea aunque la facturación sea rechazada

El sistema SHALL crear y dejar pagada la `pos.order` del Kiosko cuando el pago se
aprueba, con independencia de que la creación de la factura (`account.move`)
falle. La facturación SHALL ejecutarse aislada en un `savepoint`; si lanza, se
captura y la orden queda en estado **pendiente de facturar** (`state='paid'`,
`to_invoice=True`, `account_move` vacío), conservando su línea de pago. La
resiliencia SHALL aplicarse en el seam de facturación del Kiosko (gateada a
`self_ordering_mode == 'kiosk'`), de modo que sea independiente del método de
pago. Un pago aprobado NUNCA debe perderse por un fallo de facturación.

#### Scenario: La facturación es rechazada tras aprobar el pago

- **GIVEN** una caja en modo Kiosko, un pago aprobado, y una condición que hace
  fallar la creación de la factura (p. ej. secuencia SENIAT o impuesto mal
  configurado)
- **WHEN** el cliente finaliza y el servidor registra la orden
- **THEN** la `pos.order` queda creada y pagada con su `pos.payment`, en estado
  `paid` con `to_invoice=True` y sin `account_move`, se emite el resultado de pago
  exitoso, y el cliente ve la pantalla de confirmación

#### Scenario: La facturación es exitosa (camino feliz)

- **GIVEN** una caja en modo Kiosko con el pago aprobado y la configuración fiscal
  correcta
- **WHEN** el servidor registra la orden
- **THEN** la orden queda facturada (`account_move` creado) exactamente igual que
  antes de este cambio, sin diferencias observables en el camino feliz

#### Scenario: El fallo de factura no arrastra el pago ni el picking

- **GIVEN** una orden del Kiosko cuya facturación falla dentro del `savepoint`
- **WHEN** el `savepoint` revierte la facturación
- **THEN** la línea de pago, el estado `paid` y el picking/costo de la orden
  permanecen (solo se revierte el `account.move`), y el request se commitea con la
  orden pendiente de facturar

### Requirement: La verificación de pago Megasoft se persiste como prueba durable

El sistema SHALL persistir en la `pos.payment` la respuesta del VPOS de Megasoft
que aprobó el cobro (JSON crudo y un subconjunto para mostrar: número de
autorización, referencia, lote, tarjeta enmascarada, tipo de tarjeta,
banco/autorizador y código de respuesta), y SHALL exponer esos datos al cliente
del Kiosko para el panel de recuperación.

#### Scenario: El pago aprobado guarda su verificación

- **GIVEN** un pago Megasoft del Kiosko aprobado por el VPOS con su JSON de
  respuesta
- **WHEN** el servidor registra el pago
- **THEN** la `pos.payment` guarda el JSON crudo y los campos extraídos
  (autorización, referencia, lote, tarjeta, banco, código de respuesta)

#### Scenario: El panel puede mostrar el método verificado

- **GIVEN** una orden del Kiosko con un pago Megasoft persistido
- **WHEN** el cliente del Kiosko carga la orden en el panel de recuperación
- **THEN** los campos Megasoft del pago llegan al cliente (vía
  `_load_pos_self_data_fields`) y el panel muestra el método y sus datos de
  verificación

### Requirement: No se imprime la factura fiscal si la contable está pendiente

El sistema SHALL abstenerse de auto-imprimir la factura fiscal en la confirmación
(`confirmationPage`) cuando la orden aún no tiene `account_move` (factura contable
pendiente). Esas órdenes quedan **pendientes por facturar en la máquina fiscal** y
se imprimen desde el panel de recuperación una vez creada la factura contable.

#### Scenario: Orden pagada sin factura contable llega a la confirmación

- **GIVEN** una orden del Kiosko `state='paid'` sin `account_move` (facturación
  pendiente) y la máquina fiscal conectada
- **WHEN** el cliente llega a `confirmationPage`
- **THEN** NO se dispara la impresión fiscal automática; la orden queda pendiente
  de fiscal y disponible en el panel de recuperación

#### Scenario: Orden facturada sigue imprimiéndose en la confirmación

- **GIVEN** una orden del Kiosko facturada (`account_move` presente) sin
  `mf_invoice_number`
- **WHEN** el cliente llega a `confirmationPage`
- **THEN** la impresión fiscal automática ocurre como hasta ahora (comportamiento
  de `pos-self-order-kiosk-fiscal-print` sin cambios para el caso facturado)

### Requirement: Facturación diferida idempotente por endpoint público

El sistema SHALL ofrecer un endpoint público del Kiosko para crear la factura de
una orden pendiente, que valide el `access_token` y que la orden pertenezca a la
caja, y que sea idempotente (si la orden ya tiene `account_move`, no crea una
segunda). Devuelve el resultado para que el panel refresque el estado.

#### Scenario: Crear la factura de una orden pendiente

- **GIVEN** una orden del Kiosko pendiente de facturar (paid, sin `account_move`),
  con la causa del rechazo ya corregida
- **WHEN** se invoca el endpoint de facturación con el `access_token` de la caja y
  el id de la orden
- **THEN** el servidor crea el `account.move`, la orden pasa a facturada, y se
  devuelve `{success: true, invoice_id}`

#### Scenario: Reintento sobre una orden ya facturada

- **GIVEN** una orden del Kiosko que ya tiene `account_move`
- **WHEN** se invoca de nuevo el endpoint de facturación
- **THEN** no se crea una segunda factura y se devuelve el estado actual

#### Scenario: El endpoint rechaza una orden ajena a la caja

- **GIVEN** un `access_token` de una caja y un `order_id` de otra caja
- **WHEN** se invoca el endpoint de facturación
- **THEN** no se factura nada y se devuelve un error de pertenencia

### Requirement: Recuperación de órdenes pendientes desde el panel del Kiosko

El sistema SHALL extender el panel de órdenes fiscales del Kiosko para distinguir
tres estados por orden —pendiente de factura contable, pendiente de fiscal, y
completa— mostrar el pago verificado, y ofrecer la acción adecuada a cada estado
(crear factura → imprimir fiscal → reimprimir copia).

#### Scenario: Orden pendiente de factura contable

- **GIVEN** una orden del Kiosko `paid` sin `account_move`
- **WHEN** el operador la selecciona en el panel
- **THEN** el panel la marca "pendiente factura backend", muestra el pago
  verificado, y ofrece "Crear factura"; tras crearla, ofrece "Imprimir factura
  fiscal"

#### Scenario: Orden facturada pendiente de fiscal

- **GIVEN** una orden del Kiosko con `account_move` pero sin `mf_invoice_number`
- **WHEN** el operador la selecciona
- **THEN** el panel la marca "pendiente fiscal" y ofrece "Imprimir factura fiscal"

#### Scenario: Orden completa

- **GIVEN** una orden del Kiosko con `mf_invoice_number`
- **WHEN** el operador la selecciona
- **THEN** el panel la marca "completa" y ofrece "Reimprimir copia"

### Requirement: El panel de recuperación se abre desde el menú de Debug MF

El sistema SHALL exponer el panel de órdenes fiscales del Kiosko —con las
acciones de recuperación (crear factura / imprimir / reimprimir) y el pago
verificado— desde el menú de Debug MF, disponible en modo debug (`?debug=1`). NO
se muestra un punto de entrada de cara al cliente fuera de modo debug: la
recuperación es una tarea de operador/soporte.

#### Scenario: Abrir el panel de recuperación en modo debug

- **GIVEN** un Kiosko abierto con `?debug=1`
- **WHEN** el operador abre el menú Debug MF y elige "Órdenes fiscales"
- **THEN** se abre el panel con las órdenes de la caja, su estado (pendiente
  factura / pendiente fiscal / completa) y las acciones de recuperación

#### Scenario: Sin modo debug no hay punto de entrada en el Kiosko

- **GIVEN** un Kiosko abierto sin `?debug=1`
- **WHEN** el cliente usa el Kiosko normalmente
- **THEN** no se muestra ningún botón de recuperación; las órdenes pendientes de
  facturar se resuelven desde el menú de backend (o desde el panel en modo debug)

### Requirement: Menú de backend para las órdenes de Kiosko pendientes de facturar

El sistema SHALL ofrecer en el backend de Odoo una acción de menú que liste las
órdenes de Kiosko pendientes de facturar (modo kiosko, `paid`, `to_invoice=True`,
sin `account_move`) y permita crear su factura con el mismo código idempotente que
el endpoint del Kiosko.

#### Scenario: Contabilidad ve y resuelve las pendientes

- **GIVEN** órdenes de Kiosko pendientes de facturar y un usuario de contabilidad
- **WHEN** abre el menú de órdenes pendientes de facturar
- **THEN** las ve listadas con su pago verificado y puede crear la factura de cada
  una (sin duplicar si ya tuviera `account_move`)

### Requirement: Toda orden del Kiosko se marca para facturar

El sistema SHALL forzar `to_invoice=True` en toda orden creada desde una caja
en modo Kiosko (`self_ordering_mode == 'kiosk'`), sin depender de que el
cliente del Kiosko lo envíe, replicando la regla SENIAT que `l10n_ve_pos` ya
aplica en la caja normal.

#### Scenario: El cliente del Kiosko no envía `to_invoice`

- **GIVEN** una caja en modo Kiosko con `l10n_ve_pos_self_order` instalado
- **WHEN** el servidor recibe una orden del Kiosko cuyo payload no trae
  `to_invoice` (o lo trae en `False`)
- **THEN** la orden se persiste con `to_invoice=True`

#### Scenario: El modo Autopedido móvil (mobile) no se fuerza a facturar

- **GIVEN** una caja en `self_ordering_mode == 'mobile'` (QR de mesa), sin
  garantía de `partner_id` identificado
- **WHEN** el servidor recibe una orden de ese flujo
- **THEN** `to_invoice` NO se fuerza — se respeta el comportamiento nativo, para
  no facturar contra el consumidor genérico

### Requirement: La orden del Kiosko se factura al completarse el pago

El sistema SHALL generar la factura fiscal de la orden del Kiosko al
completarse el pago aprobado, ejecutando la finalización completa del core
(`_process_saved_order`: pagada + picking + costo + factura), no solo el cambio
de estado a `paid`.

#### Scenario: Pago aprobado en el Kiosko (Megasoft) genera factura

- **GIVEN** una orden del Kiosko en estado `draft` con `to_invoice=True` y un
  método de pago Megasoft de tarjeta-presente
- **WHEN** el pago se aprueba y `_payment_request_from_kiosk` registra el pago
- **THEN** la orden queda con un `account_move` posteado a nombre del
  `partner_id` identificado, y las líneas del asiento de pago llevan
  `foreign_debit`/`foreign_credit` derivados del `foreign_amount` del pago

#### Scenario: El asiento de pago refleja el monto en moneda foránea

- **GIVEN** un pago Megasoft registrado con `foreign_amount` = total foráneo de
  la orden y `foreign_rate` = tasa de la orden
- **WHEN** se generan los asientos de pago de la factura
  (`_create_payment_moves`)
- **THEN** cada línea del asiento lleva `foreign_debit = |foreign_amount|` en el
  lado deudor y `foreign_credit = |foreign_amount|` en el acreedor, con
  `foreign_rate`/`foreign_inverse_rate` = la tasa del pago

### Requirement: La finalización del pago del Kiosko es idempotente

El sistema SHALL evitar duplicar el pago o la factura si la finalización del
pago del Kiosko se reintenta (p. ej. si se perdió la respuesta de red), pese a
que el controlador de Kiosko del core reabre la orden a `draft` en cada
llamada.

#### Scenario: Reintento antes de facturar

- **GIVEN** una orden del Kiosko con la línea de pago ya registrada pero sin
  `account_move` (la finalización falló tras registrar el pago), reabierta a
  `draft` por `process_order`
- **WHEN** el cliente reintenta el registro del pago
- **THEN** no se registra un segundo pago (línea de pago existente) y la
  finalización se completa generando la factura

#### Scenario: Reintento después de facturar

- **GIVEN** una orden del Kiosko ya facturada (`account_move` posteado) cuya
  respuesta se perdió, reabierta a `draft` por `process_order`
- **WHEN** el cliente reintenta el registro del pago
- **THEN** no se genera una segunda factura, no se registra un segundo pago, y
  el estado final de la orden se restaura (`done`/`paid`)

### Requirement: Teclado en pantalla para los campos de texto del Kiosko

El Kiosko SHALL ofrecer un componente OWL propio (`KioskKeyboard`), sin
librerías externas, con dos modos:

- **Texto**: QWERTY en español (incluida la Ñ) + fila de números + espacio +
  borrar + mayúsculas (alternable).
- **Numérico**: solo dígitos, mismo layout 3×4 (1-9, borrar/0/limpiar) que el
  numpad propio de la cédula en `IdentificationPage`.

El teclado SHALL mostrarse al enfocar un campo de texto de la pantalla de
identificación/creación de contacto (nombre, apellido, calle, teléfono) y
SHALL escribir en el campo que tiene el foco. El campo de teléfono SHALL usar
el modo numérico. El layout SHALL seguir al campo tocado cada vez (al enfocarlo
y al tocarlo aunque ya tuviera el foco), y las teclas del teclado NO SHALL
quitarle el foco al campo activo.

#### Scenario: Volver de teléfono a un campo de texto

- **GIVEN** el teclado en modo numérico tras tocar el teléfono
- **WHEN** el cliente vuelve a tocar nombre, apellido o calle
- **THEN** el teclado cambia de nuevo al modo QWERTY

#### Scenario: Enfocar un campo de texto muestra el teclado

- **GIVEN** el paso de creación de contacto del Kiosko
- **WHEN** el cliente toca el campo de nombre, apellido o calle
- **THEN** aparece el teclado QWERTY y cada tecla tocada escribe en ese campo

#### Scenario: Enfocar el teléfono muestra el modo numérico

- **GIVEN** el paso de completar teléfono o de creación de contacto
- **WHEN** el cliente toca el campo de número de teléfono
- **THEN** aparece el teclado en modo numérico (solo dígitos) y escribe en
  ese campo

#### Scenario: Mayúsculas

- **GIVEN** el teclado en modo texto
- **WHEN** el cliente activa mayúsculas y toca una letra
- **THEN** se escribe la letra en mayúscula; al desactivar mayúsculas vuelve
  a escribir en minúscula

#### Scenario: Borrar y espacio

- **GIVEN** el teclado en modo texto con un campo activo
- **WHEN** el cliente toca "borrar"
- **THEN** se borra el último carácter del campo activo
- **WHEN** el cliente toca "espacio" (y el campo activo no es el teléfono)
- **THEN** se inserta un espacio en el campo activo

#### Scenario: Limpiar en modo numérico

- **GIVEN** el teclado en modo numérico con el teléfono como campo activo
- **WHEN** el cliente toca "C"
- **THEN** se vacía el campo activo

#### Scenario: El teclado queda completo en pantalla

- **GIVEN** el formulario de cliente nuevo (nombre, apellido, teléfono,
  dirección), donde el teclado se muestra al final del formulario
- **WHEN** el teclado aparece o cambia de modo (texto ↔ numérico)
- **THEN** se desplaza a la vista para que su última fila (borrar, 0,
  limpiar) sea visible sin desplazar a mano

### Requirement: Panel de órdenes del Kiosko en base, funcional sin máquina fiscal

El sistema SHALL ofrecer, en `l10n_ve_pos_self_order`, un panel de órdenes del
Kiosko que liste las órdenes de la caja (paid/done/invoiced, con líneas) cargadas
del servidor y permita **crear la factura** de una orden pagada pendiente de
facturar. El panel SHALL funcionar con independencia de que el módulo de máquina
fiscal esté instalado. Los datos SHALL venir de una ruta pública
(`/l10n_ve_pos_self_order/kiosk/session_orders`) validada por `access_token`, en
el formato que consume `connectNewData`, sin pedir campos fiscales.

#### Scenario: Kiosko sin máquina fiscal recupera una factura

- **GIVEN** un Kiosko con `l10n_ve_pos_self_order` pero SIN
  `l10n_ve_pos_mf_self_order`, y una orden pagada pendiente de facturar
- **WHEN** el operador abre el panel de órdenes en modo debug y pulsa "Crear
  factura" sobre esa orden
- **THEN** el panel llama al endpoint `create_invoice`, la orden queda facturada
  y el panel refleja el nuevo estado, sin depender de ninguna lógica fiscal

#### Scenario: El estado "facturada" se deriva del servidor

- **GIVEN** una orden cargada desde `session_orders`
- **WHEN** el panel calcula su estado
- **THEN** la considera facturada cuando `state === "invoiced"` (señal
  autoritativa del servidor), no a partir de un flag client-side que puede no
  venir en órdenes cargadas del servidor

### Requirement: Shell de debug del Kiosko con acceso único, extensible

El sistema SHALL exponer un botón flotante de debug (visible solo con `?debug=1`)
que abra un shell de debug del Kiosko con: abrir el panel de órdenes y reintentar
el registro de órdenes de la cola durable (pendientes y fallidas). El shell SHALL
ser un único punto de entrada, extensible por otros módulos (p. ej. el fiscal
añade sus herramientas de máquina fiscal) sin agregar un segundo botón.

#### Scenario: Un solo botón de debug aunque haya módulo fiscal

- **GIVEN** un Kiosko con el módulo fiscal instalado, en modo debug
- **WHEN** el operador ve la raíz del Kiosko
- **THEN** hay UN solo botón de debug; al abrirlo, el shell muestra tanto las
  herramientas de base (órdenes, reintentos de cola) como las fiscales añadidas
  por extensión

### Requirement: Resumen de montos del Kiosko antes de pagar

El Kiosko SHALL mostrar, ANTES de que el cliente pulse Pagar, en la pantalla
del carrito (`pos_self_order.CartPage`, en lugar del "Total/Taxes" del core) o,
en modo solo escaneo/búsqueda, debajo del resumen de líneas de
`ProductListPage` (ese modo se salta el carrito),
un resumen con: base imponible, desglose de impuestos por tasa (una fila por
cada `account.tax.group` presente en la orden — IVA 16%, 8%, exento, lo que
aplique) y el total en la moneda local (Bs.). Cuando la compañía tenga una
moneda foránea configurada (`res.company.foreign_currency_id`) SHALL mostrar
también el total en esa moneda, calculado con la MISMA tasa operativa que usa
`pos.order.recompute_prices` (server-side, `l10n_ve_pos_self_order/models/pos_order.py`)
para fijar `foreign_amount_total` en la orden ya pagada — así el monto que el
cliente ve antes de pagar coincide con el que termina en la factura.

El resumen NO SHALL ir en la pantalla de pago: con un único método de pago
(la configuración recomendada, un solo método Megasoft cuyo VPOS deja elegir
tarjeta/pago móvil/transferencia) el core lo auto-selecciona al montar
`PaymentPage` y el VPOS abre de inmediato, sin que se pueda leer nada. Ese
salto directo al VPOS SHALL conservarse.

#### Scenario: Base, impuestos y total en Bs.

- **GIVEN** una orden del Kiosko con líneas gravadas a distintas tasas
- **WHEN** el cliente revisa su orden antes de pagar
- **THEN** ve la base imponible, una fila por cada tasa de impuesto presente
  y el total en Bs.

#### Scenario: Total en moneda foránea

- **GIVEN** una compañía con `foreign_currency_id` configurada
- **WHEN** el cliente revisa su orden antes de pagar
- **THEN** ve también el total en esa moneda, rotulado "Total <código de la
  moneda>" (p. ej. "Total USD", "Total EUR" según `foreign_currency_id`),
  calculado con los mismos
  helpers de `l10n_ve_pos` que usa la caja (`get_foreign_total_with_tax`,
  tasa operativa de `pos.config` y redondeo de la moneda), y ese monto coincide con el
  `foreign_amount_total` que termina en la factura de la orden

#### Scenario: Sin moneda foránea configurada

- **GIVEN** una compañía sin `foreign_currency_id`
- **WHEN** el cliente revisa su orden antes de pagar
- **THEN** no se muestra la fila de total en moneda foránea

#### Scenario: Un solo método Megasoft

- **GIVEN** el Kiosko con un único método de pago Megasoft
- **WHEN** el cliente pulsa Pagar tras ver el resumen
- **THEN** el VPOS abre directamente, sin pantalla intermedia

### Requirement: Teléfono venezolano obligatorio y validado

El Kiosko SHALL pedir el teléfono del cliente como un código de operadora
móvil venezolana (uno de `0412`, `0414`, `0416`, `0422`, `0424`, `0426`,
elegido en un desplegable) más un número de exactamente 7 dígitos. El
teléfono SHALL ser obligatorio tanto al crear un contacto nuevo como al
completar el teléfono faltante de un contacto existente. El valor SHALL
guardarse en `res.partner.phone` compuesto como
`"<código>-<7 dígitos>"` (p. ej. `"0414-1234567"`).

La validación de formato SHALL ejecutarse en el cliente (para dar
retroalimentación inmediata) y SHALL repetirse en el servidor
(`controllers/orders.py`, rutas `identify/create` y `identify/set_phone`),
sin confiar en lo que el cliente ya validó.

#### Scenario: Teléfono con formato válido

- **GIVEN** el paso de creación de contacto o de completar teléfono
- **WHEN** el cliente elige un código de operadora válido y escribe 7 dígitos
- **THEN** el teléfono se guarda como `"<código>-<7 dígitos>"`

#### Scenario: Código de operadora no reconocido

- **GIVEN** el paso de creación de contacto o de completar teléfono
- **WHEN** el cliente no elige un código de operadora de la lista
- **THEN** se rechaza con un mensaje de error, tanto en cliente como en
  servidor si se fuerza la llamada

#### Scenario: Número con largo distinto de 7 dígitos

- **GIVEN** un código de operadora válido
- **WHEN** el número tiene menos o más de 7 dígitos, o contiene caracteres
  no numéricos
- **THEN** se rechaza con un mensaje de error, tanto en cliente como en
  servidor

#### Scenario: Teléfono vacío

- **GIVEN** el paso de creación de contacto o de completar teléfono
- **WHEN** el cliente no completa el teléfono
- **THEN** no se puede continuar: al pulsar el botón se muestra el motivo
  (operadora sin elegir o número incompleto) y el servidor también lo rechaza
  si se llama directamente. El botón NO se deshabilita por datos incompletos
  (solo mientras hay una petición en curso), para que el cliente siempre vea
  qué le falta

#### Scenario: Caracteres no válidos o de más en el número

- **GIVEN** el campo de número de teléfono
- **WHEN** el cliente teclea una letra o un octavo dígito
- **THEN** el carácter no aparece en el campo (el valor saneado se reescribe
  también en el input, no solo en el estado)
- **AND** mientras el número tenga menos de 7 dígitos se muestra bajo el campo
  el aviso "El número de teléfono debe tener exactamente 7 dígitos."

### Requirement: Barra de progreso de pasos en el Kiosko

El sistema SHALL mostrar en el Kiosko (`self_ordering_mode == 'kiosk'`) una barra
de progreso fija en la parte superior con los pasos del flujo de autopedido
(Identificación, Productos, Pago), resaltando el paso correspondiente a la
pantalla activa.

#### Scenario: El paso resaltado sigue a la pantalla activa

- **GIVEN** una caja en modo Kiosko con `l10n_ve_pos_self_order` instalado
- **WHEN** el cliente navega entre las pantallas del flujo (identificación →
  productos/carrito → pago)
- **THEN** la barra resalta el paso correspondiente (1 en `identification`; 2 en
  `product_list`/`product`/`combo_selection`/`cart`; 3 en `payment`), con los
  pasos previos marcados como completados

#### Scenario: La barra no aparece fuera del flujo de pedido

- **GIVEN** una caja en modo Kiosko
- **WHEN** la pantalla activa es la de bienvenida (`default`)
- **THEN** la barra de progreso no se muestra

#### Scenario: El modo móvil/QR no muestra la barra

- **GIVEN** una caja en `self_ordering_mode == 'mobile'` (QR)
- **WHEN** el cliente usa el autopedido
- **THEN** la barra de progreso de pasos no se muestra (es exclusiva del Kiosko)

### Requirement: Leyenda de campos obligatorios en los pasos de contacto

Los pasos de "completar teléfono" y "nuevo cliente" de `IdentificationPage` SHALL mostrar la leyenda "LOS CAMPOS MARCADOS CON * SON OBLIGATORIOS" encima
de los campos del formulario. El texto fuente SHALL ser traducible vía
`_t()`; el marcador "*" de cada campo individual (nombre, apellido, teléfono)
SHALL seguir agregándose fuera del término traducible base (p. ej.
`_t("Phone") + " *"`), sin alterar el msgid del término.

#### Scenario: Paso de completar teléfono

- **GIVEN** un cliente identificado por cédula sin teléfono registrado
- **WHEN** llega al paso de completar teléfono
- **THEN** ve la leyenda de campos obligatorios encima del campo teléfono

#### Scenario: Paso de nuevo cliente

- **GIVEN** una cédula no encontrada
- **WHEN** el cliente llega al paso de creación de contacto
- **THEN** ve la leyenda de campos obligatorios encima de los campos del
  formulario (nombre, apellido, teléfono)

### Requirement: Ajuste opcional "solo escaneo / búsqueda" por punto de venta

El punto de venta SHALL exponer un ajuste booleano
`self_ordering_hide_catalog`, editable en Ajustes solo cuando el modo de
autopedido es `kiosk`. El ajuste SHALL enviarse al frontend del Kiosko. Con el
ajuste desactivado, el Kiosko SHALL comportarse igual que el nativo (catálogo
visible, sin saludo ni buscador).

#### Scenario: Ajuste visible solo en modo Kiosko

- **GIVEN** la pantalla de Ajustes de un punto de venta
- **WHEN** el modo de autopedido es `kiosk`
- **THEN** se muestra el ajuste "Kiosko: solo escaneo / búsqueda"
- **WHEN** el modo es distinto de `kiosk`
- **THEN** el ajuste no se muestra

#### Scenario: Sin el ajuste, catálogo nativo

- **GIVEN** un Kiosko con `self_ordering_hide_catalog` desactivado
- **WHEN** el cliente llega a la lista de productos
- **THEN** ve el catálogo completo (categorías + grilla) sin saludo ni buscador

### Requirement: Ocultar el catálogo y ofrecer buscador en el Kiosko

La página de lista de productos del Kiosko SHALL ocultar el catálogo y ofrecer un buscador cuando el modo es `kiosk` y `self_ordering_hide_catalog` está activo.
Con el ajuste activo SHALL ocultar la barra de categorías, la de subcategorías
y la grilla del catálogo, y SHALL mostrar un buscador de texto. El buscador
SHALL filtrar los `product.template` disponibles (`self_order_available`) por
nombre, `display_name`, código de barras o referencia interna, con un tope de
resultados. Los resultados SHALL renderizarse con las mismas tarjetas del
catálogo, y tocar un resultado SHALL añadirlo al carrito con el mismo
comportamiento que el catálogo (incluidos combos y productos configurables).

#### Scenario: Catálogo oculto

- **GIVEN** un Kiosko con el ajuste activo
- **WHEN** el cliente llega a la lista de productos
- **THEN** no se muestran las categorías ni la grilla del catálogo, y sí un
  buscador de texto

#### Scenario: Buscar por nombre o código

- **GIVEN** el buscador visible
- **WHEN** el cliente escribe parte del nombre, código de barras o referencia de
  un producto disponible
- **THEN** se muestran los productos coincidentes (hasta el tope) como tarjetas
- **WHEN** ninguna coincide
- **THEN** se muestra el mensaje de "sin resultados"

#### Scenario: Añadir desde un resultado

- **GIVEN** una tarjeta de resultado de búsqueda
- **WHEN** el cliente la toca
- **THEN** el producto se añade al carrito igual que en el catálogo (los combos
  y configurables abren su paso correspondiente), y el buscador se limpia tras
  añadir un producto simple

### Requirement: Escaneo por lector siempre disponible y sin salir de la pantalla

El escaneo por lector de código de barras SHALL seguir funcionando en el modo
"solo escaneo / búsqueda" (buscar por `barcode` y añadir al pedido). A
diferencia del Kiosko nativo, escanear NO SHALL navegar al carrito: el cliente
SHALL permanecer en la pantalla de escaneo/búsqueda, donde el producto aparece
en el resumen en-sitio. Ocultar el catálogo NO SHALL deshabilitar el escaneo.

#### Scenario: Escanear con el catálogo oculto

- **GIVEN** un Kiosko con el ajuste activo y un lector de código de barras
- **WHEN** el cliente escanea un producto disponible
- **THEN** el producto se añade al pedido y el cliente permanece en la pantalla
  de escaneo/búsqueda (no salta al carrito)

### Requirement: Pago directo sin pasar por el carrito

El botón de pago del modo escaneo/búsqueda SHALL llevar directamente a la pantalla de métodos de pago, omitiendo la pantalla intermedia de resumen del pedido (carrito).
Esta omisión SHALL aplicar solo cuando el catálogo está oculto. También SHALL
ejecutar las mismas validaciones que el carrito nativo (verificación de
disponibilidad y de datos del cliente) antes de proceder. Si faltaran datos
requeridos del cliente, SHALL recurrir al flujo completo del carrito para
recogerlos.

#### Scenario: Pagar salta al pago

- **GIVEN** un pedido con líneas en la pantalla de escaneo/búsqueda y un cliente
  identificado
- **WHEN** el cliente pulsa el botón de pago
- **THEN** va directamente a la pantalla de métodos de pago, sin mostrar el
  resumen/carrito intermedio

#### Scenario: Datos incompletos recurren al carrito

- **GIVEN** un pedido cuyo cliente no cumple los datos requeridos
- **WHEN** el cliente pulsa el botón de pago
- **THEN** se abre el flujo completo del carrito para completar la información

### Requirement: Resumen del pedido en-sitio

Cuando el catálogo está oculto y el cliente no está buscando, la pantalla SHALL
mostrar el resumen del pedido actual en el área central (donde de otro modo iría
la pista de escaneo). Cada línea SHALL mostrar nombre, cantidad y precio, con
controles para aumentar/disminuir la cantidad y eliminar la línea. El resumen
SHALL actualizarse en vivo al escanear o añadir productos. Si hay una búsqueda
activa, SHALL mostrarse en su lugar la grilla de resultados.

#### Scenario: El pedido aparece al añadir

- **GIVEN** un Kiosko con el ajuste activo y sin búsqueda activa
- **WHEN** el cliente escanea o añade un producto
- **THEN** el producto aparece en el resumen del pedido en el área central

#### Scenario: Editar cantidades desde el resumen

- **GIVEN** una línea en el resumen en-sitio
- **WHEN** el cliente aumenta/disminuye la cantidad o elimina la línea
- **THEN** el resumen y los totales se actualizan en consecuencia

#### Scenario: La búsqueda tiene prioridad sobre el resumen

- **GIVEN** un pedido con líneas
- **WHEN** el cliente escribe en el buscador
- **THEN** se muestran los resultados de búsqueda (para añadir), no el resumen

### Requirement: Saludo personalizado al cliente identificado

Cuando el modo es `kiosk` y el catálogo está oculto, la página SHALL mostrar
arriba un saludo "¡Hola {nombre}!" usando el nombre del contacto del pedido
actual (`currentOrder.partner_id`). Si no hubiera nombre, SHALL mostrar un
saludo genérico ("¡Hola!"). El texto SHALL ser traducible vía `_t()`.

#### Scenario: Cliente identificado por cédula

- **GIVEN** un Kiosko con el ajuste activo donde el cliente ya se identificó por
  cédula al inicio
- **WHEN** llega a la lista de productos
- **THEN** ve "¡Hola {nombre del contacto}!" encima del buscador

#### Scenario: Sin nombre disponible

- **GIVEN** un pedido sin contacto con nombre
- **WHEN** se muestra la página con el catálogo oculto
- **THEN** se muestra el saludo genérico "¡Hola!"
