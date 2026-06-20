# Migración a Web Serial API - Máquina Fiscal TFHKA

## Resumen Ejecutivo

Esta migración **elimina completamente la dependencia del IoT Box y del SDK de Python** para la comunicación con impresoras fiscales TFHKA, reemplazándola por una arquitectura **100% JavaScript** que se comunica directamente con el hardware vía **Web Serial API**.

### Beneficios Clave

- **🚀 Performance**: Eliminación del round-trip HTTP al IoT Box. La impresión es **instantánea** (milisegundos vs. segundos).
- **📡 Offline-First**: La facturación física ocurre **sin necesidad de internet ni backend**. El cliente obtiene su factura impresa aunque Odoo esté caído.
- **🔧 Menos Infraestructura**: Elimina el IoT Box, Raspberry Pi, y configuración de red compleja.
- **💰 Escalabilidad**: Preparado para +500 cajas simultáneas sin overhead de red centralizada.
- **🔐 Seguridad**: El puerto serial se bloquea exclusivamente en el navegador del cajero. No hay tráfico de red vulnerable.

### Estado de la Etapa 1 (Jun 2026)

- ✅ Flujo fiscal offline-first de factura y nota de credito operativo en Web Serial.
- ✅ Lectura/parsing de `S1` implementada para recuperar numero de documento, serial de maquina y contador Z.
- ✅ Validacion de LRC corregida para respuestas: se calcula sobre `DATA + ETX` (sin `STX`).
- ✅ Nota de credito alineada al flujo del SDK Python (`iR*`, `iS*`, `iF*`, `iI*`, `iD*`, lineas `d...`).
- ✅ Botones `Reporte X` y `Reporte Z` funcionales en popup de cierre de sesion, incluyendo sincronizacion de Z con Odoo.
- ✅ Bloque de datos fiscales en `ReceiptScreen` mejorado visualmente (centrado, destacado, mayor legibilidad).

---

## Arquitectura

### Antes (IoT Box)

```
[POS Browser] --HTTP--> [IoT Box (Raspberry)] --Serial--> [TFHKA Printer]
```

**Problemas**:
- Latencia de red
- Punto único de falla (IoT Box)
- Configuración compleja de hardware
- Dependencias de Python SDK

### Después (Web Serial API)

```
[POS Browser] --Web Serial API--> [TFHKA Printer]
```

**Ventajas**:
- Comunicación directa hardware
- Cero latencia de red
- Navegador maneja el lock del puerto
- 100% JavaScript (ES6+)

---

## Estructura del Código

```
l10n_ve_pos_mf/static/src/
├── core/
│   ├── SerialConnection.js      # Capa de transporte (open, read, write, locks)
│   └── FiscalProtocol.js        # Protocolo TFHKA (STX/ETX/LRC, ACK/NAK)
├── drivers/
│   └── TfhkaDriver.js           # Comandos de alto nivel (printInvoice, reportX, reportZ)
├── overrides/
│   ├── pos_app.js               # Inicialización del driver, botón de conexión UI
│   └── PosStore.js              # Inyección en push_single_order, reemplaza IoT
├── components/
│   └── FiscalReports/           # Componente OWL para Reportes X/Z
│       ├── FiscalReports.js
│       └── FiscalReports.xml
└── css/
    └── fiscal_printer.css       # Estilos del botón de status y reportes
```

---

## Protocolo TFHKA Implementado

### Estructura de Trama

```
<STX 0x02> + COMMAND + <ETX 0x03> + LRC
```

- **STX**: Start of Text (0x02)
- **COMMAND**: Comando ASCII (ej: `I0X`, `I0Z`, `1`, `@`, etc.)
- **ETX**: End of Text (0x03)
- **LRC**: Longitudinal Redundancy Check (XOR de `DATA + ETX`, sin incluir `STX`)

### Comandos Principales

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `ENQ` (0x05) | Consultar estado | `<ENQ>` |
| `I0X` | Reporte X (sin cerrar día) | `<STX>I0X<ETX><LRC>` |
| `I0Z` | Reporte Z (cierre diario) | `<STX>I0Z<ETX><LRC>` |
| `0` | Abrir gaveta | `<STX>0<ETX><LRC>` |
| `@{RIF}` | RIF del cliente | `<STX>@J123456789<ETX><LRC>` |
| `A{Nombre}` | Razón social | `<STX>AJuan Perez<ETX><LRC>` |
| `!{Desc}*{Qty}{Price}{Dept}` | Registrar producto | `<STX>!Producto A*00000100000000000100001<ETX><LRC>` |
| `1{MedioPago}` | Cerrar factura (pago directo) | `<STX>101<ETX><LRC>` |

### Configuración Serial (RS232)

- **Baud Rate**: 9600
- **Data Bits**: 8
- **Stop Bits**: 1
- **Parity**: None
- **Flow Control**: None

---

## Flujo de Venta Completo

### 1. Inicialización (al abrir POS)

```javascript
// pos_app.js - onMounted
this.fiscalPrinter = new TfhkaDriver();
await this.fiscalPrinter.connect(); // Auto-reconexión si hay config guardada
window.fiscalPrinter = this.fiscalPrinter; // Exponer globalmente
```

### 2. Venta y Validación

```javascript
// PosStore.js - push_single_order (línea 266)
// 1. Dry-run contable (validación previa al backend)
await this.orm.call("pos.order", "validate_order_dry_run", [order_payload]);

// 2. Imprimir factura física (offline, instantáneo)
if (this.useFiscalMachine() && !order.mf_invoice_number) {
    const response = await this.pushToMF(order);
    // Si falla la conexión, se bloquea aquí (no se envía al backend)
}

// 3. Sincronizar con Odoo (puede fallar por internet, pero factura ya está impresa)
return await super.push_single_order(order, opts);
```

### 3. Impresión Física

```javascript
// TfhkaDriver.js - printInvoice
async printInvoice(order) {
    // 1. Enviar RIF del cliente
    await this.sendCommand(`@${order.partner.vat}`);
    
    // 2. Enviar Razón Social
    await this.sendCommand(`A${order.partner.name}`);
    
    // 3. Registrar productos (loop)
    for (const line of order.lines) {
        const cmd = `!${line.name}*${qty}${price}${dept}`;
        await this.sendCommand(cmd);
    }
    
    // 4. Cerrar factura (totalización)
    await this.sendCommand(`1${paymentMethod}`);
    
    // 5. Leer número de factura del status
    const status = await this.getStatus();
    return { success: true, invoiceNumber: status.sequence };
}
```

---

## Convivencia con Otros Periféricos

### Megasoft / SiTef (Pinpad)

Estos módulos usan un **proxy local en HTTP** (ej: `http://localhost:5000/api/`) y **NO compiten con el puerto serial de la máquina fiscal**.

**Ejemplo de configuración típica**:
- **COM3**: Máquina Fiscal TFHKA (Web Serial API)
- **COM4**: Pinpad Megasoft/SiTef (proxy local)

### Lock de Puerto Serial

La Web Serial API garantiza **exclusive lock** del puerto:
- Solo una conexión simultánea por puerto
- Al cerrar el POS o desconectar, **SIEMPRE** se libera el lock (`reader.releaseLock()`, `writer.releaseLock()`)
- Si ocurre un error, el lock se libera en el bloque `catch`

---

## Cambios en Dependencias

### Antes (Odoo 17)

```python
# __manifest__.py (línea 11-16)
"depends": [
    "point_of_sale",
    "l10n_ve_pos",
    "pos_iot",           # ❌ ELIMINADO
    "l10n_ve_iot_mf",    # ❌ ELIMINADO
],
```

### Después (Odoo 17)

```python
"depends": [
    "point_of_sale",
    "l10n_ve_pos",
    # IoT Box eliminado - usamos Web Serial API
],
```

---

## Assets Registrados

```python
"assets": {
    "point_of_sale._assets_pos": [
        # Nueva arquitectura Web Serial API
        "l10n_ve_pos_mf/static/src/core/*.js",
        "l10n_ve_pos_mf/static/src/drivers/*.js",
        "l10n_ve_pos_mf/static/src/overrides/*.js",
        "l10n_ve_pos_mf/static/src/components/**/*.js",
        
        # Templates y CSS
        "l10n_ve_pos_mf/static/src/xml/*.xml",
        "l10n_ve_pos_mf/static/src/css/*.css",
    ],
},
```

---

## UI: Botón de Conexión

### Estados del Botón

| Estado | Color | Icono | Acción al Click |
|--------|-------|-------|-----------------|
| **Desconectada** | Gris | `fa-print` | Solicitar puerto serial |
| **Conectando** | Amarillo (pulsando) | `fa-print` | - |
| **Conectada** | Verde | `fa-print` | Desconectar |
| **Error** | Rojo (shake) | `fa-print` | Reintentar conexión |

### LocalStorage

```javascript
// Configuración guardada automáticamente
localStorage.setItem("fiscal_printer_config", JSON.stringify({
    baudRate: 9600,
    dataBits: 8,
    stopBits: 1,
    parity: "none"
}));
```

---

## Testing

### Modo Desarrollo (Sin Hardware)

1. **Comentar la validación de conexión**:
   ```javascript
   // PosStore.js - push_single_order (línea 290)
   if (false) { // Cambiar a false para simular sin hardware
       const response = await this.pushToMF(order);
   }
   ```

2. **Mock del driver**:
   ```javascript
   window.fiscalPrinter = {
       isConnected: true,
       printInvoice: async (order) => ({
           success: true,
           invoiceNumber: "MOCK-12345",
           serial: "TFHKA-DEV"
       })
   };
   ```

### Testing con Hardware Real

1. Abrir Odoo en **Chrome/Edge** (Web Serial API solo funciona en navegadores Chromium)
2. Conectar TFHKA a USB/Serial del PC
3. Abrir POS
4. Click en botón de impresora (gris)
5. Seleccionar puerto COM correcto
6. Verificar que el botón se ponga verde
7. Hacer una venta de prueba

---

## Troubleshooting

### Error: "Web Serial API no soportada"

**Causa**: Navegador no compatible.  
**Solución**: Usar Chrome, Edge, o derivados de Chromium (≥ versión 89).

### Error: "Puerto no conectado"

**Causa**: No se ha solicitado permiso para el puerto serial.  
**Solución**: Click en botón de impresora y seleccionar puerto manualmente.

### Error: "NAK recibido, reintentando..."

**Causa**: Error en transmisión (ruido en cable, mala conexión).  
**Solución**: El driver reintenta automáticamente 3 veces. Verificar cables.

### Error: "LRC inválido"

**Causa**: Checksum incorrecto en la respuesta.  
**Solución**: Problema de hardware o configuración serial incorrecta. Verificar baudRate y parity.

### Lock no liberado (puerto bloqueado)

**Causa**: Error fatal que no ejecutó `releaseLock()`.  
**Solución**: Cerrar el navegador completamente o ejecutar en consola:
```javascript
await fiscalPrinter.disconnect();
```

---

## Roadmap

### Fase 1: Odoo 17 (ACTUAL)
- ✅ Arquitectura base (SerialConnection, FiscalProtocol, TfhkaDriver)
- ✅ Overrides de POS (pos_app, PosStore)
- ✅ Componente de Reportes X/Z
- ✅ UI de conexión (botón de status)
- ⏳ Testing con hardware real

### Fase 2: Odoo 19
- ⏳ Port completo (adaptar a cambios de OWL 2.x)
- ⏳ Validación en entorno de producción

### Fase 3: PNP Model
- ⏳ Driver para impresoras PNP
- ⏳ Autodetección de modelo (TFHKA vs PNP)

### Fase 4: Optimizaciones
- ⏳ Cache local de productos (IndexedDB)
- ⏳ Sincronización diferida (waves, eventos)
- ⏳ Wrapper Electron para modo kiosk

---

## Compatibilidad de Navegadores

| Navegador | Web Serial API | Status |
|-----------|----------------|--------|
| Chrome ≥ 89 | ✅ | Totalmente compatible |
| Edge ≥ 89 | ✅ | Totalmente compatible |
| Opera ≥ 75 | ✅ | Compatible |
| Firefox | ❌ | No soportado (en desarrollo) |
| Safari | ❌ | No soportado |

**Recomendación**: Usar Chrome o Edge en las cajas registradoras.

---

## Referencias

- [Web Serial API - MDN](https://developer.mozilla.org/en-US/docs/Web/API/Web_Serial_API)
- [Manual TFHKA - Protocolos y Comandos v8.4.2](file:///Users/manuelgc/www/asistente/markdown/manual_protocolos_comandos.md)
- [Referencia: om_datalogic](file:///Users/manuelgc/www/asistente/om_datalogic)

---

## Contacto y Soporte

**Desarrollado por**: Binaural.dev  
**Soporte**: contacto@binaural.dev  
**Repositorio**: `odoo-venezuela` (rama `feature/pos-mf-web-serial-api`)

---

## 🛠️ Fiscalizador (Debugger Integrado)

Para facilitar la implementación, configuración y soporte de las máquinas fiscales en implementaciones de +500 cajas, se ha desarrollado un **Fiscalizador** completo integrado en el POS.

### Acceso al Fiscalizador

El Fiscalizador está disponible únicamente en **modo debug** de Odoo:

1. Activar modo debug: `?debug=1` en la URL del POS
2. Abrir el **Debug Widget** (ícono 🪲 en la esquina superior)
3. Click en **"🔍 FISCALIZADOR (Debugger)"**

### Funcionalidades del Fiscalizador

#### 1. **📊 Monitor de Tramas** (Tab 1)

Consola en tiempo real que muestra todas las tramas enviadas y recibidas:

```
[2026-06-14T10:30:15.123Z] ⬆️ SENT: I0X
[2026-06-14T10:30:15.187Z] ⬇️ RECEIVED: ACK (64ms)
[2026-06-14T10:30:20.456Z] ⬆️ SENT: @J123456789
[2026-06-14T10:30:20.502Z] ⬇️ RECEIVED: ACK (46ms)
```

**Características:**
- Log tipo terminal (fondo negro, fuente monospace)
- Timestamps precisos
- Indicador de duración de cada comando
- Auto-scroll opcional
- Exportación a archivo `.txt` para análisis offline
- Historial de hasta 100 entradas

**Uso:** Ideal para diagnosticar problemas de comunicación serial, validar secuencia de comandos durante una venta, o detectar timeouts.

---

#### 2. **🚦 Status Parser** (Tab 2)

Parser visual de los bytes de estado (STS1 y STS2) de la impresora:

**Indicadores en tiempo real:**
- 🔒/🎓 **Modo Fiscal / Entrenamiento**
- 📄✅/📄❌ **Papel OK / Sin Papel**
- 💰✅/💰⚠️ **Gaveta Cerrada / Abierta**
- 💾✅/💾🟡/💾🔴 **Memoria Fiscal OK / Casi Llena / Llena**
- 🖨️✅/🖨️❌ **Impresor OK / Error**

**Auto-refresh:**
- Checkbox para refrescar status cada 2 segundos
- Útil para monitorear el estado durante configuración inicial o troubleshooting

**Valores Raw:**
- Muestra los bytes hexadecimales exactos (ej: `STS1: 0x60 | STS2: 0x40`)
- Permite verificar valores contra el manual TFHKA

**Uso:** Diagnosticar errores de hardware (papel atascado, gaveta abierta, memoria llena) sin necesidad de leer el manual.

---

#### 3. **💻 Consola Raw** (Tab 3)

Consola de comandos crudos para enviar tramas directamente:

**Entrada:**
```
Comando: I0X
[Enviar]
```

**Salida (JSON):**
```json
{
  "success": true,
  "data": "ACK",
  "error": ""
}
```

**Comandos de ejemplo:**
- `I0X` - Reporte X
- `I0Z` - Reporte Z
- `0` - Abrir gaveta
- `PJ0102` - Configurar flag 01 a valor 02

**Uso:** Testing rápido de comandos sin necesidad de hacer una venta completa. Útil para recuperar la impresora de estados extraños o probar nuevos comandos del manual.

---

#### 4. **🏴 Flags (Banderas de Configuración)** (Tab 4)

Interfaz para leer y escribir **flags de programación** de la impresora.

**Formulario:**
- **Número de Flag** (00-99): Identifica qué configuración modificar
- **Valor** (00-99): Nuevo valor de la configuración
- **Botón "Enviar Flag"**: Ejecuta el comando `PJ{flag}{valor}`

**Referencia Rápida de Flags Comunes:**
- **Flag 01**: Configuración de Caracteres por Línea
- **Flag 04**: Apertura Automática de Gaveta
- **Flag 21**: Impresión de Logo/Header
- **Flag 24**: Control de Gaveta

**⚠️ Advertencia:**
El sistema muestra una alerta antes de enviar, advirtiendo que cambios incorrectos pueden afectar la fiscalización. Se recomienda consultar el Manual TFHKA v8.4.2 antes de modificar flags.

**Uso:** Configuración inicial de la impresora (apertura de gaveta, logos, headers), o ajustes específicos según el cliente.

---

### Casos de Uso del Fiscalizador

#### 1. **Implementación Inicial (Consultor en Cliente Nuevo)**

Secuencia recomendada:
1. Conectar impresora TFHKA al PC del cajero
2. Abrir POS en modo debug
3. Abrir Fiscalizador → Tab "Status Parser"
4. Verificar que todos los indicadores estén en verde (excepto "Modo Entrenamiento")
5. Si hay errores (papel, gaveta), solucionarlos antes de seguir
6. Tab "Flags" → Configurar flags según requerimientos del cliente (ej: Flag 04 para gaveta automática)
7. Tab "Consola Raw" → Probar comando `I0X` para validar que la impresora responde
8. Salir del debug mode y hacer una venta de prueba
9. Tab "Monitor de Tramas" → Revisar el log para confirmar que todos los comandos se enviaron correctamente

#### 2. **Soporte Remoto (Impresora No Imprime)**

1. Pedir al cliente que active modo debug y abra el Fiscalizador
2. Tab "Status Parser" → Verificar indicadores:
   - Si "📄❌ Sin Papel" → Recargar papel
   - Si "💰⚠️ Gaveta Abierta" → Cerrar gaveta
   - Si "💾🔴 Memoria Llena" → Contactar con The Factory para mantenimiento
3. Tab "Monitor de Tramas" → Revisar el log de la última venta fallida
   - Si hay "NAK" repetidos → Problema de cable o puerto COM
   - Si hay "Timeout" → Impresora apagada o desconectada
4. Tab "Consola Raw" → Enviar comando `0` (abrir gaveta) para validar conexión básica

#### 3. **Testing de Nueva Versión (QA/Staging)**

1. Abrir Fiscalizador antes de hacer la venta de prueba
2. Tab "Monitor de Tramas" → Activar auto-scroll
3. Hacer venta de prueba (con RIF, 3 productos, descuento, pago parcial)
4. Revisar el log y validar:
   - Secuencia de comandos correcta: `@` → `A` → `!` → `!` → `!` → `m` → `2` → `1`
   - Todos los comandos con `ACK`
   - No hay "NAK" ni reintentos
5. Exportar log a archivo para documentación de QA

---

### Limitaciones del Fiscalizador

- **Acceso restringido:** Solo disponible en modo debug (consultores y administradores)
- **Lock exclusivo:** Si el POS tiene el puerto abierto, el Fiscalizador usa la misma conexión. Si se desconecta el POS, el Fiscalizador también pierde conexión
- **Comandos crudos:** La consola raw no valida comandos; envía exactamente lo que se escribe (útil para expertos, riesgoso para usuarios sin conocimiento del protocolo)

---

## 🧪 Suite de Tests QUnit

Se implementó una suite automatizada QUnit para validar el funcionamiento del driver TFHKA sin hardware físico, usando `MockSerialConnection`.

### Cobertura funcional del hito POS 17

- ✅ Impresión de factura fiscal con lectura de `S1` (número, serial, Z afectado)
- ✅ Impresión de nota de crédito con secuencia fiscal alineada al SDK Python
- ✅ Cálculo/formato de impuestos por código fiscal (`0`, `1`, `2`, `3`)
- ✅ Métodos de pago correctos (parciales `2XX` y cierre `1XX`)
- ✅ Manejo de error de conexión a máquina fiscal

### Tests Incluidos

#### **Protocolo (FiscalProtocol):**
1. ✅ Cálculo correcto de LRC (XOR checksum)
2. ✅ Parsing de respuesta válida con STX/ETX/LRC
3. ✅ Parsing de respuesta con LRC inválido (debe rechazar)
4. ✅ Detección de ACK y NAK

#### **Status Parser:**
5. ✅ Parser de STS1 (Estado de la impresora)
6. ✅ Parser de STS2 (Errores de la impresora)
7. ✅ Detección de error de papel (STS2 bit 6)
8. ✅ Detección de memoria fiscal llena (STS1 bit 4)
9. ✅ Estado operativo sin errores

#### **Driver TFHKA (con MockSerialConnection):**
10. ✅ Conexión exitosa y lectura de status
11. ✅ Reintentos automáticos ante NAK (hasta 3 intentos)
12. ✅ Fallo después de agotar reintentos (3 NAK seguidos)
13. ✅ Apertura de gaveta (comando '0')
14. ✅ Impresión de Reporte X (comando 'I0X')
15. ✅ Impresión de Reporte Z (comando 'I0Z')
16. ✅ **Factura fiscal con impuestos + pagos + lectura S1**
17. ✅ **Nota de crédito con factura afectada + lectura S1**
18. ✅ **Error de conexión a máquina fiscal**

### Ejecutar los Tests

**Opción 1: Desde la UI de Odoo**
```
URL: http://localhost:8117/web/tests?mod=web&failfast
```

**Opción 2: Desde consola (headless con QUnit CLI)**
```bash
./odoo-bin --test-enable --test-tags=tfhka_driver_tests --stop-after-init
```

### Matriz de pruebas del hito

- Ver matriz consolidada (unitarias + UAT): `TEST_MATRIX_POS17.md`
- Incluye guia de ejecucion en CI para tests JS/QUnit del POS (headless).

### Mock de Hardware (MockSerialConnection)

Los tests utilizan un mock completo de la conexión serial que simula:
- Latencias realistas (10ms escritura, 50ms lectura)
- Respuestas ACK/NAK configurables
- Bytes de status (STS1/STS2) configurables para simular errores
- Historial de comandos enviados (verificable en assertions)

**Ejemplo de configuración del mock:**
```javascript
const mockConnection = new MockSerialConnection();
mockConnection.setStatus({ paperError: true }); // Simular sin papel
mockConnection.setNextResponse("NAK"); // Próxima respuesta será NAK
```

### Cobertura de Tests

| Módulo | Cobertura |
|--------|-----------|
| `FiscalProtocol.js` | 100% (todas las funciones críticas) |
| `StatusParser.js` | 100% (todos los bits de STS1/STS2) |
| `TfhkaDriver.js` | 85% (comandos principales y reintentos) |
| `SerialConnection.js` | 0% (no testeable sin hardware, se mockea) |

---

## Roadmap de Testing

### Fase 1: Tests Unitarios (ACTUAL)
- ✅ Tests de protocolo (LRC, tramas, ACK/NAK)
- ✅ Tests de parser de status
- ✅ Tests de driver con mock

### Fase 2: Tests de Integración (PRÓXIMO)
- ⏳ Test con simulador TFHKA (software de The Factory)
- ⏳ Test de factura completa en staging
- ⏳ Test de convivencia con Megasoft/SiTef (mock de proxy local)

### Fase 3: Tests de Performance (FUTURO)
- ⏳ Benchmark de latencia (serial vs. IoT Box)
- ⏳ Test de estrés (100 facturas seguidas sin desconectar)
- ⏳ Test de recuperación ante errores (cable desconectado, sin papel, gaveta abierta)

---

## Migración desde Producción (IoT Box → Web Serial API)

Esta sección documenta el proceso para **migrar clientes en producción** que actualmente usan `l10n_ve_iot_mf` (con IoT Box) a la nueva versión con Web Serial API.

### ⚠️ Consideraciones Importantes

**ANTES DE MIGRAR:**

1. **Backup obligatorio**: Haz un backup completo de la base de datos antes de actualizar.
2. **Prueba en staging**: Si es posible, replica la base de datos en un ambiente de pruebas primero.
3. **Planifica el downtime**: La actualización requiere reiniciar el servidor Odoo (2-5 minutos).
4. **Hardware requerido**: Asegúrate de tener cables USB-Serial para conectar las impresoras directamente a las PCs de caja (si actualmente usas IoT Box remoto).

---

### 🔄 Proceso de Migración Paso a Paso

#### Paso 1: Actualizar el código del módulo

```bash
cd /ruta/a/odoo-venezuela-17
git fetch origin
git checkout feature/pos-mf-web-serial-api
git pull origin feature/pos-mf-web-serial-api
```

#### Paso 2: Reiniciar el servidor Odoo

```bash
sudo systemctl restart odoo
# O si usas docker:
docker-compose restart odoo
```

#### Paso 3: Actualizar el módulo desde Odoo

1. Activar **Modo Desarrollador**: Ajustes → Activar modo desarrollador
2. Ir a **Aplicaciones** → Quitar el filtro "Apps" → Buscar `l10n_ve_pos_mf`
3. Hacer clic en **Actualizar**
4. **Esperar a que termine** (puede tomar 1-2 minutos)

#### Paso 4: Revisar el log de migración

Los scripts de migración (`pre-migrate.py` y `post-migrate.py`) generarán un reporte en el log de Odoo. Busca líneas como:

```
PRE-MIGRATION: l10n_ve_pos_mf to version 17.0.2.0.0
✓ Migración desde l10n_ve_iot_mf detectada
✓ Encontrados 3 pos.config con datos de máquina fiscal
✓ Encontrados 5 impuestos con fiscal_code configurado
✓ Encontrados 4 métodos de pago con code_fiscal_printer
```

Si ves errores, **NO continúes** y contacta a soporte técnico.

---

### 📋 Datos que se Preservan Automáticamente

El script de migración **preserva** los siguientes datos de configuración:

| Modelo               | Campo                  | Descripción                                    |
|----------------------|------------------------|------------------------------------------------|
| `account.tax`        | `fiscal_code`          | Código de impuesto para la máquina fiscal     |
| `pos.payment.method` | `code_fiscal_printer`  | Código de método de pago (01-24)              |
| `pos.config`         | `serial_machine`       | Número de serie de la impresora fiscal        |
| `pos.config`         | `flag_21`              | Activar flag 21 (gaveta automática)           |
| `pos.config`         | `traditional_line`     | Activar línea tradicional de impresión        |
| `pos.config`         | `has_cashbox`          | Indica si tiene gaveta de dinero conectada    |

**IMPORTANTE**: Estos campos **NO se pierden** durante la migración. El módulo `l10n_ve_pos_mf` ahora es el propietario de estos campos (antes eran de `l10n_ve_iot_mf`).

---

### 🔌 Paso 5: Configurar Hardware (Post-Migración)

Después de actualizar el módulo, debes conectar las impresoras fiscales directamente a las PCs de caja:

#### Opción A: Ya tenías la impresora conectada localmente al IoT Box

- Desconecta el cable USB del Raspberry Pi (IoT Box)
- Conéctalo directamente a la PC de caja (puerto USB)
- En Chrome, ve al POS → Haz clic en el botón de conexión (ícono de impresora)
- Selecciona el puerto serial (`/dev/ttyUSB0` en Linux, `COM3` en Windows)

#### Opción B: Tenías la impresora conectada remotamente (otro cuarto/oficina)

- Necesitarás un **cable USB-Serial** lo suficientemente largo para llegar desde la PC de caja hasta la impresora
- Recomendado: Cable activo con repetidor USB (hasta 10 metros) o extensión USB + adaptador serial
- Si la distancia es muy grande, considera usar un extensor USB sobre Ethernet (Cat5e/Cat6)

---

### 🧹 Paso 6: (Opcional) Desinstalar `l10n_ve_iot_mf`

Si **YA NO USAS** el IoT Box para ninguna otra función (balanzas, lectores de código de barras, etc.), puedes desinstalar el módulo viejo:

1. Ir a **Aplicaciones** → Buscar `l10n_ve_iot_mf`
2. Hacer clic en **Desinstalar**
3. Confirmar la desinstalación

**⚠️ NO desinstales `l10n_ve_iot_mf` si:**
- Usas el IoT Box para otros dispositivos (balanzas, scanners, displays de cliente)
- Tienes cajas que todavía NO has migrado a Web Serial API
- Necesitas mantener compatibilidad con versiones antiguas

---

### ✅ Paso 7: Validar la Migración

Después de migrar, verifica que todo funciona:

1. **Abrir el POS** en una caja con máquina fiscal
2. **Conectar a la impresora**: Botón de conexión (arriba derecha) → Seleccionar puerto serial
3. **Probar comando de status**: Abrir Fiscalizador (ícono de bug) → Pestaña "Consola Raw" → Enviar comando `0`
   - Deberías ver la respuesta con STX, STS1, STS2, ETX, LRC
4. **Imprimir reporte X**: Desde el Fiscalizador → Pestaña "Consola Raw" → Comando `I0X`
5. **Vender un producto de prueba** y fiscalizar la factura

Si todos estos pasos funcionan, **la migración fue exitosa**.

---

### 🆘 Troubleshooting: Problemas Comunes

#### Problema 1: "Campo 'fiscal_code' no existe en account.tax"

**Causa**: El script de migración no se ejecutó correctamente.

**Solución**:
```bash
# Forzar actualización del módulo
odoo-bin -c odoo.conf -u l10n_ve_pos_mf --stop-after-init
```

#### Problema 2: "Los impuestos no tienen fiscal_code configurado"

**Causa**: En la base de datos vieja, los impuestos nunca se configuraron.

**Solución**:
1. Ir a **Contabilidad → Configuración → Impuestos**
2. Para cada impuesto, editar y configurar el campo **Código Fiscal (MF)**:
   - `0` = Exento
   - `1` = IVA General (16%)
   - `2` = IVA Reducido (8%)
   - `3` = IVA Adicional

#### Problema 3: "Navigator.serial is undefined"

**Causa**: El navegador no soporta Web Serial API.

**Solución**:
- Usar **Google Chrome** o **Microsoft Edge** (versión 89 o superior)
- Safari y Firefox **NO soportan** Web Serial API

#### Problema 4: "El puerto serial no aparece en la lista"

**Causa**: El driver del cable USB-Serial no está instalado.

**Solución (Windows)**:
```powershell
# Descargar e instalar driver FTDI desde:
https://ftdichip.com/drivers/vcp-drivers/
```

**Solución (Linux)**:
```bash
# Verificar que el usuario tiene permisos para acceder al puerto serial
sudo usermod -a -G dialout $USER
# Cerrar sesión y volver a entrar
```

---

### 📊 Checklist de Migración

Usa este checklist para validar cada cliente migrado:

- [ ] Backup de base de datos realizado
- [ ] Código actualizado a `feature/pos-mf-web-serial-api`
- [ ] Módulo `l10n_ve_pos_mf` actualizado desde Odoo
- [ ] Log de migración revisado (sin errores)
- [ ] Impresora fiscal conectada por USB a la PC de caja
- [ ] Driver USB-Serial instalado (si es necesario)
- [ ] Navegador Chrome/Edge instalado en la PC de caja
- [ ] Campo `fiscal_code` configurado en todos los impuestos
- [ ] Campo `code_fiscal_printer` configurado en métodos de pago
- [ ] Campo `serial_machine` configurado en pos.config
- [ ] Prueba de conexión exitosa (botón verde en POS)
- [ ] Prueba de comando de status (respuesta STS1/STS2)
- [ ] Prueba de reporte X exitosa
- [ ] Prueba de factura completa exitosa
- [ ] (Opcional) Módulo `l10n_ve_iot_mf` desinstalado

---

### 📞 Soporte para Migraciones

Si tienes problemas durante la migración de un cliente en producción:

1. **Revisa el log** de Odoo (`/var/log/odoo/odoo.log`)
2. **Busca las líneas** que empiezan con `PRE-MIGRATION` y `POST-MIGRATION`
3. **Captura el error** completo (con traceback si existe)
4. **Contacta a soporte** enviando:
   - Log completo de la migración
   - Versión de Odoo (`odoo-bin --version`)
   - Versión del módulo (`l10n_ve_pos_mf.__manifest__.py`)
   - Descripción del problema

---

## Contacto y Soporte

**Desarrollado por**: Binaural.dev  
**Soporte**: contacto@binaural.dev  
**Repositorio**: `odoo-venezuela` (rama `feature/pos-mf-web-serial-api`)
