## ADDED Requirements

### Requirement: REQ-DON-018 · Certificado de la recepción y Recibo de la entrega
El **Certificado de donación** es el documento de una donación RECIBIDA (lo recibe el donante) y el **Recibo de donación** el de una donación OTORGADA (lo recibe el beneficiario), en dinero (`account.move`) y en mercancía (`stock.picking`). `print_donation_certificate` imprime el certificado y `print_donation_receipt` el recibo; cada método DEBE (MUST) rechazar el documento de la otra dirección con un error que indica el que corresponde, y los botones se muestran según la dirección.

#### Scenario: Cada documento en su dirección
- **Dado** un asiento de donación recibida y uno de donación otorgada, publicados
- **Cuando** se imprime el certificado y el recibo de cada uno
- **Entonces** el certificado solo se imprime en la recibida y el recibo solo en la otorgada; el otro falla indicando el documento que corresponde

### Requirement: REQ-DON-019 · Recibo de donación estandarizado
El recibo DEBE (MUST) tener una estructura única para el dinero y la mercancía: encabezado de la compañía, número y fecha, datos del beneficiario (nombre, RIF o cédula, dirección y teléfono) (el RIF es el del contacto comercial: un contacto hijo usa el RIF y el prefijo de su empresa), monto con equivalente y tasa, concepto (en dinero, las líneas de gasto; en mercancía, la tabla de productos compartida con lote, vencimiento y costo), observaciones (referencia del asiento o motivo de donación), constancia de donación y firmas, en media hoja carta. Los elementos `donation_receipt_beneficiary_extra` y `donation_receipt_legal` DEBEN (MUST) existir para que otros módulos agreguen datos (paciente, texto legal) por herencia.

#### Scenario: Recibo de una entrega
- **Dado** una entrega de donación validada con un beneficiario y un motivo
- **Cuando** se imprime el recibo
- **Entonces** muestra al beneficiario, la tabla de productos con su total al costo y el motivo como observación

### Requirement: REQ-DON-020 · Cuentas y dirección de las donaciones recibidas
La compañía DEBE (MUST) poder configurar varias cuentas de ingresos de donaciones recibidas (`donation_income_account_ids`, también en los ajustes). Un asiento es una donación recibida (`_is_incoming_donation`, `is_incoming_donation`) si es un asiento manual (`entry`) marcado `is_donation` con alguna línea en una de esas cuentas; la dirección se decide por la cuenta y no por el diario. Una factura de donación no lo es, aunque use la misma cuenta. Sin cuentas configuradas ningún asiento es recibido y el comportamiento no cambia (la recepción de mercancía tampoco exige donante ni configuración contable, REQ-DON-024). Los ajustes solo admiten cuentas de ingresos de la compañía activa (`check_company` y dominio por compañía). Como la dirección se deduce de las cuentas, NO DEBE (MUST NOT) poder agregarse ni quitarse una cuenta que use algún asiento de donación publicado de la compañía: el documento de ese asiento cambiaría entre Certificado y Recibo.

#### Scenario: Con y sin cuentas
- **Dado** un asiento manual de donación con una línea en la cuenta de ingresos
- **Cuando** la compañía no tiene cuentas configuradas, y luego se configura esa cuenta
- **Entonces** el asiento no es una donación recibida, y después sí lo es

#### Scenario: Cambio de cuentas con asientos publicados
- **Dado** una donación recibida publicada con la cuenta de ingresos configurada
- **Cuando** se intenta quitar esa cuenta (o agregar la de una donación otorgada publicada)
- **Entonces** falla con un error que indica cuántos asientos la usan; los borradores y las cuentas sin uso no bloquean el cambio

### Requirement: REQ-DON-021 · Las líneas de una donación recibida llevan al donante
Las líneas de un asiento de donación recibida DEBEN (MUST) llevar al donante como contacto. `_check_partner_donation` (compañía en las líneas) y `_fill_donation_entry_line_partner` (relleno con la compañía al crear la línea, al marcar la donación y antes de publicar) NO DEBEN (MUST NOT) aplicarse a ellas; las donaciones otorgadas conservan el contacto de la compañía en las líneas. Cuando la cabecera y las líneas traen contactos distintos, el donante del certificado es el de la cabecera (comportamiento heredado de 17: solo se validan las líneas y `_get_donation_counterparty` toma primero la cabecera).

#### Scenario: Donante en las líneas
- **Dado** un asiento de donación recibida con el donante en sus líneas
- **Cuando** se guarda
- **Entonces** se acepta y las líneas conservan al donante; la misma entrega de líneas en una donación otorgada se rechaza

#### Scenario: Cabecera distinta del donante de las líneas
- **Dado** una donación recibida cuya cabecera es otro contacto que el de sus líneas
- **Cuando** se imprime el certificado
- **Entonces** nombra al contacto de la cabecera

### Requirement: REQ-DON-022 · Validación al publicar una donación recibida
Antes de publicar, `_check_incoming_donation_before_post` (punto de extensión) se ejecuta en `_post`, así que lo cubren `action_post`, la publicación automática y cualquier publicación directa, y DEBE (MUST) verificar que todas las líneas tengan contacto, distinto de la compañía, y que sea el mismo donante en todas. La validación corre con el asiento en borrador y NO DEBE (MUST NOT) escribir nada en él: funciona en diarios con "Bloquear asientos con hash".

#### Scenario: Líneas sin donante o con donantes distintos
- **Dado** un asiento de donación recibida con una línea sin contacto, o con la compañía, o con dos donantes
- **Cuando** se publica
- **Entonces** falla con un mensaje que indica el donante y el asiento sigue en borrador

### Requirement: REQ-DON-023 · Certificado de donación recibida en dinero
El certificado del asiento (`l10n_ve_donation.action_donation_certificate_account_move`) DEBE (MUST) declarar la recepción de "la suma de" el monto (REQ-DON-026) del donante (nombre, RIF o cédula del contacto comercial, domicilio y teléfono, `_get_donation_counterparty`: la cabecera o el contacto de las líneas), con descripción del uso y tipo de donativo en blanco, destino de la donación, fecha y firmas. Los elementos `donation_certificate_legal` (datos del representante legal de la compañía) y `donation_certificate_extra` DEBEN (MUST) existir como puntos de extensión. La fecha del certificado, y la de la tasa que dice, DEBE (MUST) ser la fecha contable del asiento (`date`, la de su tasa), no `invoice_date`: en el asiento de una línea de extracto de un día anterior, `invoice_date` es el día en que se concilió y no corresponde a la tasa impresa.

#### Scenario: Certificado al donante
- **Dado** una donación recibida en dinero, publicada
- **Cuando** se imprime el certificado
- **Entonces** muestra al donante con su RIF y domicilio, la suma recibida y no menciona bienes

#### Scenario: Línea de extracto de un día anterior
- **Dado** una línea de extracto del 19/11 conciliada el 20/11 contra una cuenta de donaciones recibidas, con fecha contable 19/11
- **Cuando** se imprime el certificado
- **Entonces** dice «tasa BCV del día 19/11/2026», con la tasa de ese día y su monto en USD, y la fecha de cierre es la misma; no sale el 20/11

### Requirement: REQ-DON-024 · Recepción de donaciones de mercancía
Cuando la compañía tiene cuentas de donaciones recibidas (REQ-DON-020), una recepción de donación sin pedido (`is_donation`, entrante) DEBE (MUST) tener al donante ("Recibir de") para validarse; sin cuentas la recepción valida como antes, sin donante ni configuración contable. Con productos de valoración automatizada, `_get_donation_receipt_config_errors` (punto de extensión) DEBE (MUST) exigir, solo cuando la compañía tiene cuentas de donaciones recibidas, que el origen sea una ubicación de tipo Pérdida de inventario y que su cuenta de valoración sea una de ellas: el asiento de valoración (core 19: crédito = cuenta de la ubicación de origen cuando la tiene) queda Debe inventario / Haber ingreso por donación. Una entrega de donación NO DEBE (MUST NOT) tener como destino una ubicación cuya cuenta sea de donaciones recibidas. Un picking nuevo abierto desde la tarjeta de un tipo de donación queda marcado como donación.

#### Scenario: Recepción correcta
- **Dado** una recepción de un producto `real_time` desde "Donaciones recibidas" con la cuenta de ingresos como cuenta de valoración
- **Cuando** se valida
- **Entonces** el asiento de valoración acredita la cuenta de ingresos y debita el inventario

#### Scenario: Compañía sin cuentas de donaciones recibidas
- **Dado** una compañía sin cuentas de donaciones recibidas y una recepción de donación sin donante, desde cualquier origen
- **Cuando** se valida
- **Entonces** valida como una recepción normal, sin exigir donante ni configuración contable

#### Scenario: Configuración incoherente
- **Dado** una recepción cuyo origen no es de pérdida de inventario, no tiene cuenta, o tiene una que no es de donaciones recibidas
- **Cuando** se valida
- **Entonces** falla con un mensaje que indica qué corregir

### Requirement: REQ-DON-025 · Certificado de la recepción de mercancía
El certificado de una recepción (`l10n_ve_donation.action_donation_certificate_stock_picking`) DEBE (MUST) listar los productos con la tabla compartida (lote, vencimiento y costo desde `stock.move.value`) y el total al costo de todas sus líneas con su equivalente (`_get_donation_picking_amounts`): el total por la tasa guardada en el primer asiento de valoración publicado, o por la tasa de la fecha del documento cuando no hay asientos (sin tasa se omite el equivalente), de modo que una reimpresión da los mismos datos aunque el picking mezcle productos con y sin valoración automatizada. El equivalente es siempre el monto en bolívares entre la tasa del día guardada en el asiento, y NO DEBE (MUST NOT) leerse de los dólares de las líneas del asiento, que pueden traer un valor histórico distinto (producto comprado a otra tasa). Bajo la tabla, que muestra el total en la moneda de la compañía, el "Equivalent value" DEBE (MUST) ser el valor en la otra moneda: el monto en bolívares cuando la compañía está en USD y el equivalente en USD cuando está en bolívares; el monto en bolívares nunca falta (REQ-DON-026). Las líneas se calculan una vez por documento (`_get_donation_goods_data`). El botón y `print_donation_certificate` se ofrecen solo en recepciones de donación `done` de una compañía con cuentas de donaciones recibidas (`has_donation_income_accounts`); sin cuentas la recepción es inerte y no tiene certificado.

#### Scenario: Certificado de una recepción
- **Dado** una recepción de donación validada
- **Cuando** se imprime el certificado
- **Entonces** muestra al donante, los productos con su total al costo y "los siguientes bienes"

#### Scenario: Compañía en USD con alterna en bolívares
- **Dado** una recepción de donación de una compañía en USD con alterna en bolívares
- **Cuando** se imprime el certificado
- **Entonces** bajo la tabla (en USD) se muestra el monto en bolívares como "Equivalent value" con la tasa BCV

#### Scenario: Compañía sin cuentas de donaciones recibidas
- **Dado** una recepción de donación `done` de una compañía sin cuentas de donaciones recibidas
- **Cuando** el usuario abre el picking o invoca `print_donation_certificate`
- **Entonces** no ve el botón y el método falla indicando que se deben configurar las cuentas

#### Scenario: Picking con productos de las dos valoraciones
- **Dado** una recepción con un producto de valoración automatizada (costo 10) y otro de valoración periódica (costo 5)
- **Cuando** se imprime el certificado
- **Entonces** el monto es 15 y el equivalente es 15 por la tasa del asiento de valoración

### Requirement: REQ-DON-026 · Monto y tasa de los documentos de donación
Los documentos DEBEN (MUST) mostrar el monto en bolívares primero (`_compute_donation_amounts`): la moneda de la compañía si está en bolívares, la alterna si la compañía está en otra moneda (como USD), con su equivalente en la otra moneda y la tasa BCV guardada en el asiento (bolívares por unidad de esa moneda), de modo que una reimpresión dé los mismos datos. La tasa DEBE (MUST) elegirse según cuál moneda es el bolívar: `foreign_rate` si la compañía está en bolívares y `foreign_inverse_rate` si la alterna lo es. Sin monto alterno o sin tasa se omite el equivalente.

#### Scenario: Compañía en USD con alterna en bolívares
- **Dado** una compañía en USD con alterna VEF y un monto de 84,44 USD (38.000,00 VEF)
- **Cuando** se imprime un documento
- **Entonces** el monto en bolívares va primero y la tasa es 450,0000 bolívares por USD, no su inversa

### Requirement: REQ-DON-027 · Beneficiario de una donación otorgada en dinero
En un asiento manual de donación otorgada (`is_donation`, `entry`, no recibida) el formulario DEBE (MUST) mostrar el contacto de la cabecera como "Beneficiary" (editable en borrador; no se muestra en las recibidas, donde el donante va en las líneas). Las líneas siguen con la compañía: las que copian el contacto de la cabecera al crearse (o al marcar la donación) se reemplazan por la compañía, y un contacto distinto en una línea sigue rechazándose (`_check_partner_donation`). El Recibo de donación DEBE (MUST) mostrar al beneficiario (nombre, RIF o cédula y dirección).

#### Scenario: Donación otorgada con beneficiario
- **Dado** un asiento manual de donación otorgada con un contacto en la cabecera y sin contacto en las líneas
- **Cuando** se guarda y se publica
- **Entonces** se acepta, la cabecera conserva al beneficiario, las líneas quedan con la compañía y el Recibo muestra al beneficiario

#### Scenario: Marcar la donación después
- **Dado** un asiento manual con un contacto en la cabecera y sin la marca de donación (sus líneas copiaron el contacto comercial de la cabecera)
- **Cuando** se marca "Es Donación"
- **Entonces** se acepta y las líneas quedan con la compañía; el reemplazo corre antes de escribir la marca porque la restricción corre dentro de la escritura

### Requirement: REQ-DON-028 · Guardas de impresión de los documentos
Los métodos `print_donation_receipt` y `print_donation_certificate` DEBEN (MUST) revisar el documento antes de imprimir, sin depender de la visibilidad de los botones: en `account.move`, que sea un asiento manual (`entry`) de donación publicado, el recibo de una otorgada y que no sea el asiento de valoración de una entrega, el certificado de una recibida; en `stock.picking`, que sea una donación sin pedido y `done`, el recibo de una entrega (saliente) y el certificado de una recepción (entrante). Cada negación DEBE (MUST) fallar con un error que indica el documento que corresponde. El asiento de reversión de otro (`reversed_entry_id` lleno) NO DEBE (MUST NOT) tener documento: copia la marca y las cuentas del original, pero los documentos pertenecen al original.

#### Scenario: Documentos que no son donación
- **Dado** una factura, un asiento normal, un asiento de donación en borrador y un picking de donación sin hacer
- **Cuando** se invoca el método de impresión
- **Entonces** falla con un error sin generar el documento

#### Scenario: Reversión de una donación
- **Dado** el asiento de reversión de una donación publicada (copia la marca y las cuentas del original)
- **Cuando** se invoca el método de impresión o se abre el formulario
- **Entonces** el método falla indicando que el documento es el del asiento original y los botones no se ofrecen; el original conserva su Recibo o Certificado

### Requirement: REQ-DON-029 · Cuentas de gasto de donaciones
La compañía DEBE (MUST) poder configurar las cuentas de gasto que puede usar una donación otorgada (`donation_expense_account_ids`, many2many de cuentas de gasto de la compañía, también en los ajustes) y una cuenta de gasto en especie por defecto (`donation_account_id`), que DEBE (MUST) ser una de ellas cuando hay lista. La cuenta por defecto es la que propone la ubicación de pérdida de inventario del almacén de donación y la de la nota de crédito de una venta de donación. Con cuentas en la lista: un asiento manual de donación otorgada en dinero (no recibida, ni de valoración, ni reversión) DEBE (MUST) tener una línea en una de ellas para publicarse, y la cuenta de valoración del destino de una entrega de donación con productos de valoración automatizada DEBE (MUST) ser una de ellas. Sin cuentas no hay restricción y el comportamiento no cambia. Al guardar los Ajustes, la cuenta por defecto se compara con la lista una sola vez, cuando todos los campos están escritos (se escriben uno por uno y sin un orden fijo). El módulo NO DEBE (MUST NOT) crear cuentas: se configuran.

#### Scenario: Donación en dinero con una cuenta fuera de la lista
- **Dado** una compañía con una cuenta de gasto en la lista y un asiento de donación otorgada cuyo gasto está en otra cuenta
- **Cuando** se publica
- **Entonces** falla indicando las cuentas de la lista; con una línea en una cuenta de la lista se publica

#### Scenario: Cuenta por defecto fuera de la lista
- **Dado** una lista de cuentas de gasto
- **Cuando** la cuenta en especie por defecto no está en ella (o se quita de la lista)
- **Entonces** se rechaza el cambio

### Requirement: REQ-DON-030 · El asiento de la recepción de mercancía es una donación recibida
El asiento de valoración de una recepción de donación (`is_donation`, sin pedido, entrante, con cuentas de donaciones recibidas en la compañía) DEBE (MUST) quedar marcado `is_donation`, igual que el de una entrega (`stock.move._is_donation_move`, un solo método para las dos direcciones; sin cuentas la recepción es inerte y el asiento no se marca). Las entregas y las recepciones que se validan juntas se valoran aparte (el core crea un solo asiento por conjunto de movimientos y uno mixto sería una donación recibida). Así queda como donación recibida: sus líneas conservan al donante, solo el Gestor de Donaciones lo revierte y no se ofrece «Restablecer a borrador». Esas dos restricciones DEBEN (MUST) comprobarse también en el servidor (`_reverse_moves` y `button_draft`, que alcanzan la acción de la lista y las llamadas RPC) para los asientos manuales de donación, y no solo ocultar los botones; el asiento del extracto bancario puede restablecerse a borrador (la conciliación lo hace) y lo que corre como superusuario no se restringe. El asiento de valoración NO DEBE (MUST NOT) tener documento propio (ni Recibo ni Certificado): el documento se imprime desde el picking; `print_donation_certificate` DEBE (MUST) rechazarlo como ya lo hace `print_donation_receipt`.

#### Scenario: Recepción validada
- **Dado** una recepción de donación con cuentas de recibidas
- **Cuando** se valida
- **Entonces** su asiento queda marcado como donación recibida, un usuario que no es Gestor no puede revertirlo y su certificado se imprime solo desde el picking

### Requirement: REQ-DON-031 · Donación en dinero por el extracto bancario
El asiento de una línea de extracto bancario (`statement_line_id`) que se concilia contra una cuenta de donaciones recibidas DEBE (MUST) quedar marcado `is_donation` solo cuando sus líneas ACREDITAN una cuenta de donaciones recibidas (un pago al donante, con débito a esa cuenta, no es una donación recibida), sin restablecerlo a borrador. La marca se reevalúa cada vez que cambian las líneas (conciliar, cambiar la cuenta, deshacer la conciliación): la marca automática (`donation_marked_from_statement`) se quita cuando el asiento deja de ser una donación recibida y la que puso una persona no se toca. La marca se escribe en el asiento tal como está, en una sola escritura por conjunto y sin marcarlo como modificado a mano, y NO DEBE (MUST NOT) exigir al donante para publicar ni la restricción del contacto de las líneas de una donación otorgada (la conciliación no puede fallar por eso). Un asiento manual no se marca por sus cuentas, y sin cuentas de donaciones recibidas nada se marca.

#### Scenario: Conciliación contra el ingreso por donaciones
- **Dado** una línea de extracto con el donante como contacto
- **Cuando** se concilia contra una cuenta de donaciones recibidas
- **Entonces** su asiento es una donación recibida y ofrece el certificado con el donante

#### Scenario: Se deshace la conciliación
- **Dado** el asiento marcado por la conciliación
- **Cuando** se deshace la conciliación o se cambia la cuenta de ingreso por otra
- **Entonces** la marca se quita sola y el asiento se puede volver a conciliar

### Requirement: REQ-DON-032 · Formato de los documentos de donación
Los documentos DEBEN (MUST) mostrar el RIF con su prefijo (`res.partner._get_donation_vat`, del contacto comercial), la dirección completa sin repetir el nombre y con el estado por su nombre (`_get_donation_address`: calle, ciudad, estado, código postal y país) para la empresa, el donante y el beneficiario, y las cantidades y montos de la tabla con el formato del idioma y de la moneda. El concepto del Recibo de dinero DEBE (MUST) ser «Donación» cuando las líneas no tienen un texto propio (distinto de la referencia). El Certificado DEBE (MUST) salir en tamaño carta y el Recibo en media carta; la migración cambia el formato del Certificado solo en las bases donde sigue en A4 (el registro es `noupdate`), sin tocar uno que se eligió a propósito.

### Requirement: REQ-DON-033 · Nota de crédito de una venta de donación en moneda extranjera
La nota de crédito automática de una factura de donación DEBE (MUST) tener la moneda de la factura: una factura de 100 USD queda revertida por una nota de 100 USD, conciliada y sin saldo por cobrar. Cuando el módulo de tarifas de factura (`account_invoice_pricelist`) está instalado, la nota DEBE (MUST) conservar también la tarifa de la factura (`pricelist_id`) y no la del cliente, que puede estar en otra moneda (un cliente compra en las dos): ese módulo exige que la tarifa y el documento de venta tengan la misma divisa y, con la tarifa del cliente, la confirmación de la factura de donación fallaba con «La tarifa y la factura deben tener la misma divisa».

#### Scenario: Cliente con la tarifa en otra moneda
- **Dado** un cliente con la tarifa en bolívares y una factura de donación en USD con su tarifa en USD (o al revés)
- **Cuando** se confirma la factura
- **Entonces** se crea y se publica la nota de crédito en USD con la tarifa en USD, la factura queda revertida y no sale el error de divisa; los cuatro cruces de tarifa del cliente y moneda de la venta funcionan igual

### Requirement: REQ-DON-034 · Botones del asiento y grupo Gestor
«Revertir asiento» DEBE (MUST) conservar la condición estándar de Odoo (solo asientos manuales publicados que no estén revertidos) y ocultarse además en los asientos de donación a quien no es Gestor. «Restablecer a borrador» DEBE (MUST) conservar la condición estándar (`show_reset_to_draft_button`) y ocultarse además en las facturas de venta y en los asientos de donación. El grupo Gestor de Donaciones DEBE (MUST) tener un privilegio propio («Donaciones», en la categoría de Contabilidad): un selector independiente del de Contabilidad en la pestaña de permisos, para que guardar la ficha del usuario con otro nivel no lo quite y para que se pueda asignar sin modo desarrollador (un grupo sin privilegio solo se dibuja en ese modo). El registro no es `noupdate` y la migración mueve el grupo al privilegio nuevo en las bases existentes; el administrador se agrega al grupo al instalar el módulo (`post_init_hook`) y no en cada actualización.

## MODIFIED Requirements

### Requirement: Certificado de donación en PDF
**Razón**: el documento del asiento de una donación otorgada pasa a ser el Recibo de donación (`print_donation_receipt`); el Certificado de donación es el de las recibidas (REQ-DON-018, 023).

### Requirement: REQ-DON-006 · Certificado de entrega de donación
**Razón**: se llama Recibo de entrega de donación y usa la estructura estandarizada (REQ-DON-019).

### Requirement: REQ-DON-016 · Certificado de donación de dinero
**Razón**: pasa a ser el Recibo de donación de dinero otorgada; el monto y la tasa quedan en REQ-DON-026.

### Requirement: REQ-DON-017 · Las donaciones no se listan en las guías de despacho
**Razón**: el recibo de entrega (no el certificado) sustituye a la guía.
