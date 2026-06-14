# Migración a Web Serial API - Máquina Fiscal TFHKA

## Resumen Ejecutivo

Esta migración **elimina completamente la dependencia del IoT Box y del SDK de Python** para la comunicación con impresoras fiscales TFHKA, reemplazándola por una arquitectura **100% JavaScript** que se comunica directamente con el hardware vía **Web Serial API**.

### Beneficios Clave

- **🚀 Performance**: Eliminación del round-trip HTTP al IoT Box. La impresión es **instantánea** (milisegundos vs. segundos).
- **📡 Offline-First**: La facturación física ocurre **sin necesidad de internet ni backend**. El cliente obtiene su factura impresa aunque Odoo esté caído.
- **🔧 Menos Infraestructura**: Elimina el IoT Box, Raspberry Pi, y configuración de red compleja.
- **💰 Escalabilidad**: Preparado para +500 cajas simultáneas sin overhead de red centralizada.
- **🔐 Seguridad**: El puerto serial se bloquea exclusivamente en el navegador del cajero. No hay tráfico de red vulnerable.

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
- **LRC**: Longitudinal Redundancy Check (XOR de todos los bytes entre STX y ETX, inclusive)

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
