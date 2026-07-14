# Guía de Instalación - l10n_ve_pos_mf (Web Serial API)

## Para Base de Datos Limpia (Testing en MacBook)

Esta guía te ayudará a instalar y configurar el módulo de Máquina Fiscal TFHKA desde cero para hacer pruebas en vivo con hardware real conectado a tu Mac.

---

## 📋 Pre-requisitos

### Hardware
- **MacBook** (cualquier modelo con macOS 10.15+)
- **Impresora Fiscal TFHKA** (conectada a la corriente)
- **Cable Convertidor USB a Serial (RS232)**
  - Recomendado: Cables con chip **FTDI** o **Prolific** (compatibles con macOS sin drivers)
  - Si tu Mac solo tiene USB-C: Necesitarás también un adaptador USB-C a USB-A

### Software
- **Google Chrome** o **Microsoft Edge** (≥ versión 89)
  - ⚠️ **Safari y Firefox NO soportan Web Serial API**
- Odoo 17 corriendo en `http://localhost:8117` (o el puerto que uses)

---

## 1️⃣ Instalación del Módulo

### Paso 1: Actualizar Lista de Aplicaciones
1. Ve a **Aplicaciones** en Odoo
2. Click en **Actualizar Lista de Aplicaciones**
3. Confirma la actualización

### Paso 2: Instalar `l10n_ve_pos_mf`
1. Busca: `Venezuela - Integración de Punto de Venta con Maquina Fiscal`
2. Click en **Instalar**

**Dependencias que se instalarán automáticamente:**
- `point_of_sale` (Punto de Venta)
- `l10n_ve` (Localización Venezolana)
- `l10n_ve_pos` (POS Venezuela)

⚠️ **Importante:** El módulo `pos_iot` (IoT Box) **NO** se instalará ni es necesario.

---

## 2️⃣ Configuración de Odoo

### A. Configuración de la Compañía

**Navegar a:** Ajustes → Compañías → Tu Compañía

**Campos obligatorios:**
- **Nombre de la Compañía**: Ej: "EMPRESA DEMO C.A."
- **RIF**: Formato: `J123456789` (sin guiones ni espacios)
- **Dirección**: Dirección fiscal completa
- **Moneda**: Bolívares (VES) o USD según configuración

---

### B. Configuración de Impuestos

**Navegar a:** Contabilidad → Configuración → Impuestos

**Crear/Verificar estos impuestos:**

| Nombre | Tasa | Código Fiscal (`fiscal_code`) |
|--------|------|-------------------------------|
| IVA 16% | 16% | `G` (General) |
| Exento | 0% | `E` (Exento) |
| Reducido | 8% | `R` (Reducido) |

**⚠️ Crítico:** El campo `fiscal_code` debe estar configurado. La impresora TFHKA lo usa para asignar la tasa correcta a cada producto.

---

### C. Configuración de Métodos de Pago

**Navegar a:** Punto de Venta → Configuración → Métodos de Pago

Para cada método de pago que uses (Efectivo, Tarjeta, Banco), debes asignar su **Code fiscal printer**:

| Método de Pago | Code fiscal printer |
|----------------|---------------------|
| Efectivo | `01` |
| Tarjeta de Débito | `02` |
| Tarjeta de Crédito | `03` |
| Transferencia Bancaria | `04` |
| Pago Móvil | `05` |

**Cómo configurarlo:**
1. Abre el método de pago (ej: "Efectivo")
2. En el campo **Code fiscal printer**, escribe `01`
3. Guarda

⚠️ **Sin este código, la impresora rechazará la totalización del documento.**

---

### D. Configuración del Punto de Venta

**Navegar a:** Punto de Venta → Configuración → Punto de Venta

**Campos importantes:**
- **Has Cashbox** (Tiene Caja de Efectivo): ✅ **Activado**
  - Esto permite que la gaveta se abra automáticamente al pagar con efectivo
- **Métodos de Pago**: Selecciona los métodos configurados en el paso C
- **Productos Disponibles**: Selecciona una categoría o deja "Todos los productos"

**Configuraciones del IoT Box:**
- ⚠️ **Deja TODO desmarcado**. No uses ninguna opción de "IoT Box" o "Fiscal Data Module"
- La conexión ahora se hace 100% desde el navegador (Web Serial API)

---

### E. Crear Productos de Prueba

**Navegar a:** Punto de Venta → Productos → Productos

**Crear al menos 2 productos:**

**Producto 1:**
- Nombre: `Producto Gravado`
- Precio: `100.00`
- Impuesto: `IVA 16%`
- Disponible en POS: ✅

**Producto 2:**
- Nombre: `Producto Exento`
- Precio: `50.00`
- Impuesto: `Exento`
- Disponible en POS: ✅

⚠️ **Todos los productos deben tener un impuesto asignado**, de lo contrario la impresora rechazará la línea.

---

### F. Crear Cliente de Prueba

**Navegar a:** Contactos → Crear

**Datos del cliente:**
- Nombre: `CLIENTE DE PRUEBA`
- RIF: `J987654321` (puedes usar cualquier RIF válido)
- Dirección: `Caracas, Venezuela`
- Es una Compañía: ✅

---

## 3️⃣ Prueba en Vivo con la Impresora TFHKA

### Paso 1: Conectar el Hardware

1. **Conecta la impresora TFHKA** a la corriente y enciéndela
2. **Conecta el cable USB-Serial** al puerto USB de tu MacBook
3. **Verifica la conexión:**
   - Abre la Terminal de macOS
   - Ejecuta: `ls /dev/tty.*`
   - Deberías ver algo como: `/dev/tty.usbserial-XXXX` o `/dev/tty.Bluetooth-Incoming-Port`

### Paso 2: Abrir el POS en Chrome

1. Abre **Google Chrome** (NO Safari, NO Firefox)
2. Ve a: `http://localhost:8117` (o el puerto que uses)
3. Inicia sesión en Odoo
4. Abre el **Punto de Venta** y selecciona tu configuración
5. **Activa el modo debug:** Añade `?debug=1` a la URL
   - Ejemplo: `http://localhost:8117/pos/ui?config_id=1&debug=1`

### Paso 3: Conectar la Máquina Fiscal desde el POS

1. **Busca el botón de la impresora** en la barra superior del POS
   - Es un botón con un ícono de impresora (📄)
   - Inicialmente estará **gris** (desconectado)

2. **Haz click en el botón gris**
   - Chrome abrirá un diálogo nativo: *"localhost desea conectarse a un puerto serie"*
   - En la lista, selecciona tu cable (ej: `usbserial-XXXX`, `FT232R USB UART`)
   - Click en **Conectar**

3. **Verificar conexión exitosa:**
   - El botón debería ponerse **verde** ✅
   - Tooltip: "Máquina Fiscal: Conectada"

### Paso 4: Abrir el Fiscalizador (Debugger)

1. **Abre el Debug Widget:**
   - Click en el ícono 🪲 en la esquina superior derecha del POS

2. **Abre el Fiscalizador:**
   - En el menú del Debug Widget, busca la sección **"🛠️ Máquina Fiscal (Web Serial)"**
   - Click en **"🔍 FISCALIZADOR (Debugger)"**

3. **Se abrirá un popup con 4 tabs:**
   - 📊 Monitor de Tramas
   - 🚦 Status Parser
   - 💻 Consola Raw
   - 🏴 Flags

### Paso 5: Probar Comandos Básicos

#### **Tab: 🚦 Status Parser**
1. Click en **"Refrescar Status"**
2. Deberías ver los indicadores encenderse:
   - 🎓 Modo Entrenamiento (o 🔒 Modo Fiscal si ya está fiscalizada)
   - 📄✅ Papel OK
   - 💰✅ Gaveta OK
   - 💾✅ Memoria OK
   - 🖨️✅ Impresor OK

Si ves algún indicador rojo o amarillo, resuelve el problema antes de continuar.

#### **Tab: 💻 Consola Raw**
1. En el campo "Comando", escribe: `0` (cero)
2. Click en **"Enviar"**
3. **Resultado esperado:** La gaveta debería abrirse (si tienes una conectada)
4. En "Respuesta" verás:
   ```json
   {
     "success": true,
     "data": "ACK",
     "error": ""
   }
   ```

5. Prueba ahora con: `I0X` (Reporte X)
   - **Resultado esperado:** La impresora imprimirá un reporte X en papel

#### **Tab: 📊 Monitor de Tramas**
1. Activa **Auto-scroll**
2. Haz las pruebas anteriores (`0`, `I0X`)
3. Verás el log en tiempo real:
   ```
   [2026-06-14T15:30:15.123Z] ⬆️ SENT: 0
   [2026-06-14T15:30:15.187Z] ⬇️ RECEIVED: ACK (64ms)
   [2026-06-14T15:30:20.456Z] ⬆️ SENT: I0X
   [2026-06-14T15:30:20.502Z] ⬇️ RECEIVED: ACK (46ms)
   ```

### Paso 6: Hacer una Venta de Prueba Completa

1. **Cierra el Fiscalizador** (pero deja el puerto conectado - botón verde)
2. **Añade productos al carrito:**
   - "Producto Gravado" (Qty: 2)
   - "Producto Exento" (Qty: 1)
3. **Selecciona el cliente:** "CLIENTE DE PRUEBA"
4. **Click en "Pago"**
5. **Selecciona método de pago:** Efectivo
6. **Click en "Validar"**

**¿Qué debería pasar?**
1. Odoo validará la venta (dry-run contable)
2. El driver JS enviará los comandos a la impresora:
   - `@J987654321` (RIF del cliente)
   - `ACLIENTE DE PRUEBA` (Nombre del cliente)
   - `!Producto Gravado*...` (Producto 1)
   - `!Producto Exento*...` (Producto 2)
   - `101` (Totalización con efectivo)
3. **La impresora imprimirá la factura física** 🎉
4. Odoo sincronizará la orden con el backend

**Si algo falla:**
- Abre el Fiscalizador → Tab "Monitor de Tramas"
- Revisa qué comando falló
- Verifica el error en el log

---

## 4️⃣ Configuración de Flags (Opcional)

Si necesitas configurar la impresora (ej: apertura automática de gaveta), usa el **Tab 🏴 Flags** del Fiscalizador:

**Ejemplo: Activar apertura automática de gaveta**
1. Número de Flag: `04`
2. Valor: `02` (apertura automática activada)
3. Click en **"Enviar Flag"**

Consulta el **Manual TFHKA v8.4.2** para la lista completa de flags disponibles según tu modelo.

---

## 🐛 Troubleshooting

### Error: "Web Serial API no soportada"
**Causa:** Navegador incompatible  
**Solución:** Usa Google Chrome o Microsoft Edge (≥ v89)

### Error: "Web Serial API no soportada" desde otra PC en la red
**Causa:** Contexto inseguro (`http://IP:puerto`). Web Serial solo funciona en contexto seguro (`https://`) o `localhost`.  
**Solución:**
1. Para pruebas locales, abre `chrome://flags/#unsafely-treat-insecure-origin-as-secure`
2. Agrega el origen exacto (ej: `http://192.168.1.50:8117`)
3. Reinicia Chrome
4. Alternativa recomendada para productivo: publicar Odoo por `https://`

### Error: "Máquina fiscal no conectada"
**Causa:** No se ha conectado el puerto serial  
**Solución:** Click en el botón gris de la impresora y selecciona el puerto

### Error: "No se recibió respuesta de la impresora"
**Causa:** Cable desconectado o impresora apagada  
**Solución:** 
1. Verifica que la impresora esté encendida
2. Verifica el cable USB-Serial
3. En macOS Terminal: `ls /dev/tty.*` para ver si el cable es detectado

### La gaveta no se abre
**Causa:** Flag 04 no configurado  
**Solución:** 
1. Abre Fiscalizador → Tab "Flags"
2. Flag: `04`, Valor: `02`
3. Enviar

### Error: "LRC inválido" o "NAK recibido"
**Causa:** Ruido en el cable o mala conexión  
**Solución:**
1. Usa un cable USB-Serial de mejor calidad (FTDI recomendado)
2. Reduce la longitud del cable
3. Aleja el cable de fuentes de interferencia electromagnética

### La impresora imprime pero Odoo no sincroniza
**Causa:** Error en el backend después de imprimir  
**Solución:**
1. Revisa la consola de Chrome (F12)
2. Revisa el log de Odoo (`docker logs odoo17`)
3. Verifica que los impuestos y métodos de pago estén bien configurados

---

## 📚 Referencias

- **Manual TFHKA v8.4.2:** `/Users/manuelgc/www/asistente/markdown/manual_protocolos_comandos.md`
- **Documentación de Migración:** `MIGRATION_WEB_SERIAL.md`
- **Tests QUnit:** `static/src/tests/tfhka_driver_tests.js`

---

## ✅ Checklist de Instalación

Antes de hacer la prueba en vivo, verifica que hayas completado:

- [ ] Módulo `l10n_ve_pos_mf` instalado
- [ ] Compañía con RIF configurado
- [ ] Impuestos con `fiscal_code` configurado (IVA 16%, Exento, Reducido)
- [ ] Métodos de pago con `Code fiscal printer` configurado (01, 02, 03...)
- [ ] POS con "Has Cashbox" activado
- [ ] Al menos 2 productos con impuestos asignados
- [ ] Cliente de prueba con RIF
- [ ] Cable USB-Serial conectado a la Mac
- [ ] Impresora TFHKA encendida y con papel
- [ ] POS abierto en Google Chrome con `?debug=1`
- [ ] Puerto serial conectado (botón verde)
- [ ] Fiscalizador abierto y status en verde
- [ ] Botones de **Reporte X** y **Reporte Z** visibles en la ventana de cierre de sesión

¡Listo para hacer tu primera factura fiscal con Web Serial API! 🎉
