# Protocolo de Migración: IoT Box → Web Serial API (Máquina Fiscal)

**Versión**: 2.0
**Basado en**: migración real ejecutada sobre Dialca, Grupo Kam 2 y Solumedica (backups Odoo.sh, 2026-07-04)
**Módulo objetivo**: `l10n_ve_iot_mf` v17.0.0.3.0, `l10n_ve_pos_mf` v17.0.2.0.0, `l10n_ve_mf_base` v17.0.1.0.0

> **Cambio importante en v2.0**: se corrigió la estrategia de addons. Ver sección 0. Esto **invalida el Hallazgo #3** de la v1.0 (marcado como retractado, sección 3).

---

## Novedades Funcionales (Release Notes)

Estas son las capacidades nuevas que el equipo de migración debe **validar funcionalmente** (no solo que "no haya errores"). El detalle completo de cada una está en los specs (`src/odoo-venezuela-17/module-specs/openspec/specs/<módulo>/spec.md`).

### Soporte IGTF Automático (Nuevo en `l10n_ve_mf_base`)

La impresora fiscal ahora calcula e imprime el IGTF según la Gaceta 6.687 sin necesidad de lógica contable externa.

*   **Detección automática**: si un pedido incluye al menos un pago en divisas (códigos 20-24), el driver activa el protocolo IGTF.
*   **Cierre con `199`**: en vez de enviar un cierre directo (`1XX`), se envían todos los pagos como `2XX` y se confía en el comando `199` final para que la impresora calcule el IGTF internamente.
*   **Flag 50**: la impresora física debe tener el Flag 50 en `01`. Si no, el `199` no calculará IGTF aunque Odoo lo solicite. **Verificar antes de dar el OK.**
*   **Diagnóstico**: el botón "Info IGTF (S3+S25)" del fiscalizador permite ver en tiempo real la tasa programada, el desglose IGTF del documento actual y la clasificación de medios de pago S4 (Nacional 01-19 vs Divisa 20-24).

### Líneas Informativas con Formato Venezolano (Nuevo en `l10n_ve_mf_base`)

*   Las líneas de texto que muestran montos (ej: `DESC. GLOBAL = X`) ahora usan separador de miles `.` y decimal `,`: `39.290,94`.
*   Esto es **solo visual** (líneas `iXX` del protocolo). Los comandos de pago (`2XX`) y precios (`pXX`) siguen con dígitos crudos, sin separadores ni decimales.

### Reimpresión de Documento Fiscal en POS (Corregido en `l10n_ve_pos_mf`)

*   El botón "Reimprimir Documento Fiscal" en la pantalla de pedidos (Tickets) del POS ahora funciona correctamente:
    *   Solo se activa si el pedido ya tiene número fiscal asignado.
    *   Usa la conexión Web Serial (`window.fiscalPrinter.reprintDocument()`), no el flujo legacy IoT Box.
    *   Notifica al cajero con popups de éxito/error.

### Fiscalizador MF v2.0 (Nuevo en `l10n_ve_iot_mf`)

*   Panel de diagnóstico accesible desde el menú Developer Tools (modo debug).
*   Acciones: Conectar, Estado (ENQ), Datos (S1), Medios de Pago (S4), Reporte X/Z, comando raw.
*   **Nuevo**: botón "Info IGTF (S3+S25)" para diagnóstico completo de la configuración IGTF de la máquina.
*   Systray: icono de impresora (verde = conectada, gris = desconectada, rojo = error) con auto-reconexión al cargar la página.

### Migración Automática desde IoT Box (Nuevo en `l10n_ve_iot_mf` v17.0.0.3.0)

*   Al actualizar el módulo, el script `post-migration.py` hereda automáticamente el **Flag 21** desde el `iot.device` legacy a la configuración de la compañía.
*   Se limpia la vista duplicada `fiscal_code` de la versión legacy para evitar conflictos con la vista de `l10n_ve_pos_mf`.

### Arquitectura sin Servidor Intermedio

*   **Ya no se requiere** el servicio `odoo-venezuela-iot` ni la Raspberry Pi IoT Box para imprimir fiscalmente.
*   La impresora se conecta directamente por USB al navegador (Chrome/Edge obligatorio — Firefox no soporta Web Serial).
*   El navegador pedirá permiso para acceder al puerto serial la primera vez.

### Documentación de Referencia

| Recurso | Ubicación |
|---|---|
| Spec funcional completo (driver + IGTF) | `src/odoo-venezuela-17/module-specs/openspec/specs/l10n_ve_mf_base/spec.md` |
| Spec funcional completo (POS + reimpresión) | `src/odoo-venezuela-17/module-specs/openspec/specs/l10n_ve_pos_mf/spec.md` |
| Spec funcional completo (Facturación + fiscalizador) | `src/odoo-venezuela-17/module-specs/openspec/specs/l10n_ve_iot_mf/spec.md` |

---

## 0. Arquitectura de Addons — LEER PRIMERO

Cada repo cliente (`src/custom/<cliente>`) trae **submodules propios** de `integra-addons`, `third-party-addons` y `odoo-venezuela`, cada uno pineado a un commit específico (el que ese cliente realmente tiene en producción).

**Regla de la migración**:

| Repo | Origen a usar | Por qué |
|---|---|---|
| `odoo-venezuela` | **Compartido** (`src/odoo-venezuela-17`, rama `feature/pos-mf-web-serial-api`) | Es donde vive TODO el trabajo de migración fiscal Web Serial (`l10n_ve_mf_base`, `l10n_ve_iot_mf` v17.0.0.3.0, `l10n_ve_pos_mf` v17.0.2.0.0). Usar el pin del cliente aquí **eliminaría el trabajo de esta migración**. |
| `integra-addons` | **Submodule del cliente** (`src/custom/<cliente>/integra-addons`) | Debe coincidir exactamente con lo que el cliente tiene en producción. Usar un checkout compartido/genérico introduce módulos que el cliente NO tiene (o versiones que SÍ tiene pero desactualizadas), causando errores de sintaxis JS y drift de esquema falsos. |
| `third-party-addons` | **Submodule del cliente** (`src/custom/<cliente>/third-party-addons`) | Mismo criterio que `integra-addons`. |

**Inicialización de submodules** (los repos clientes los traen vacíos por defecto):

```bash
cd src/custom/<cliente>
git submodule update --init integra-addons third-party-addons
# NO inicializar 'odoo-venezuela' — usamos el compartido a propósito
```

**`instances.json`** debe apuntar así:

```json
"addons": [
  "src/enterprise-17.0",
  "src/odoo-venezuela-17",
  "src/custom/<cliente>/integra-addons",
  "src/custom/<cliente>/third-party-addons",
  "src/custom/<cliente>"
]
```

⚠️ **Error real que causó esta corrección**: al usar el checkout compartido de `integra-addons` (rama `maintenance-17.0.1`, más nueva que el pin de cualquiera de los 3 clientes probados), apareció en el navegador:
```

## 1. Alcance

Este protocolo aplica a clientes que:
- Usan impresión fiscal desde Facturación/Contabilidad (`l10n_ve_iot_mf`), y/o
- Usan impresión fiscal desde POS (`l10n_ve_pos_mf`)
- Actualmente operan vía **IoT Box** (Raspberry Pi + `iot.device`) y migran a **Web Serial API** (conexión directa navegador ↔ impresora TFHKA por USB)

## 2. Módulos Afectados

### 2.1 `l10n_ve_iot_mf` (Facturación/Contabilidad)

| Campo/Modelo | Tipo de cambio | Detalle |
|---|---|---|
| `res.company.mf_flag_21` | Campo nuevo | Formato numérico (Flag 21) para Web Serial. Se hereda automáticamente del `iot.device` legacy vía post-migration. |
| `account.move.print_type` | Campo nuevo | `related="company_id.invoice_print_type"` (fiscal/free) |
| `account.move.mf_invoice_number/mf_serial/mf_reportz/iot_mf` | Sin cambio de esquema | Se siguen poblando igual, ahora vía Web Serial en vez de IoT longpolling |
| `l10n_ve.mf.reports.wizard` | Modelo nuevo | Wizard transiente para X/Z/rango de fecha/reimpresión |
| Vista `account_move_form` | Modificada | Botones MF al final del header; sección "Fiscal Machine" única en "Otra información" |
| `migrations/17.0.0.3.0/post-migration.py` | Script nuevo | Hereda `mf_flag_21` desde `iot_device` legacy |

### 2.2 `l10n_ve_pos_mf` (POS)

| Campo/Modelo | Tipo de cambio | Detalle |
|---|---|---|
| `pos.config.serial_machine/flag_21/has_cashbox/enable_auto_sync` | Sin cambio de esquema | Configuración de caja, ahora consumida por driver Web Serial en el navegador |
| `pos.payment.method.code_fiscal_printer` | Sin cambio | Mapeo de método de pago Odoo → código fiscal TFHKA |
| `account.move.cashbox_id` | Sin cambio | Caja POS que facturó |
| Vista `pos_config_view_form_inherit` | **Reemplazada** | La vista legacy IoT (referenciaba `iface_fiscal_data_module`) se elimina; nueva vista con Flag 21/serial/gaveta/auto-sync |

### 2.3 `l10n_ve_mf_base` (nuevo módulo compartido)

Sin modelos ni vistas — solo JS compartido (`SerialConnection`, `FiscalProtocol`, `StatusParser`, `TfhkaDriver`) consumido por `l10n_ve_iot_mf` y `l10n_ve_pos_mf`. Se auto-instala como dependencia al actualizar cualquiera de los otros dos.

---

## 3. Hallazgos Reales Durante la Migración (3 clientes)

Estos son problemas **encontrados y resueltos** durante la ejecución real. No son hipotéticos — ocurrieron en los 3 clientes probados y **se espera que ocurran en los 10 restantes**.

### Hallazgo #1 — Bug en nuestro propio script de migración (CRÍTICO, ya corregido en el repo)

**Síntoma**: El post-migration script (`mf_flag_21` heredado desde `iot.device`) no se ejecutaba.

**Causa**: El script vivía en `migrations/17.0.0.2.0/`, pero clientes con versión instalada `17.0.0.2.1` (mayor que `17.0.0.2.0`) hacen que Odoo considere esa migración "ya pasada" y la salte.

**Fix aplicado**: Carpeta renombrada a `migrations/17.0.0.3.0/` (coincide con la versión objetivo del manifest). Ya está en el repo — no requiere acción por cliente.

**Cómo detectarlo si reaparece**: revisar en el log de upgrade que aparezca la línea:
```
odoo.modules.migration: module l10n_ve_iot_mf: Running upgrade [17.0.0.3.0>] post-migration
odoo.upgrade.l10n_ve_iot_mf.17.0.0.3.0.post-migration: l10n_ve_iot_mf: mf_flag_21 heredado desde iot.device legacy (XX)
```
Si no aparece, el `mf_flag_21` no se heredó — hay que ejecutarlo manualmente (ver sección 5.4).

---

### Hallazgo #2 — Drift de esquema en `l10n_ve_payment_extension` (esperado en TODOS los clientes)

**Síntoma**:
```
ERROR: column res_company.text_header_1_municipal_retention does not exist
```

**Causa**: El backup del cliente tiene una versión de `l10n_ve_payment_extension` más antigua que el código actual (acumulación normal de meses sin actualizar). Esto NO es específico de la migración fiscal — ocurre en **cualquier** actualización de un backup viejo.

**Fix**: Incluir `l10n_ve_payment_extension` en el `-u` junto con los módulos fiscales (ver sección 5).

---

### ~~Hallazgo #3~~ — RETRACTADO en v2.0 (falso positivo por checkout compartido incorrecto)

**Síntoma original reportado**:
```
ERROR: duplicate key value violates unique constraint "res_country_state_name_code_uniq"
-- o --
ParseError: ... res_country_municipality_data.xml ... El municipio ya está registrado
```

**Causa real**: Este error **NO es un problema de los clientes**. Ocurrió porque en v1.0 del protocolo usábamos el checkout compartido `src/integra-addons-17` (rama `maintenance-17.0.1`), que trae el módulo `binaural_location` — un módulo que **ninguno de los 3 clientes probados tiene en su pin real de producción** (confirmado: `binaural_location` no existe en `src/custom/{dialca,grupokam2,solumedica}/integra-addons/`).

Los 3 clientes usan en realidad `l10n_ve_location` (módulo independiente en `src/odoo-venezuela-17`, sin dependencia de `binaural_location`), que ya tiene su propio `ir_model_data` sano y completo.

**Qué pasó**: al forzar la carga del `binaural_location` "fantasma" (presente solo en el checkout compartido, no en la realidad del cliente), Odoo intentaba re-crear 25 estados y 334 municipios que YA EXISTÍAN (creados por `l10n_ve_location`), chocando con el constraint UNIQUE por duplicado de código/nombre.

**Acción tomada**: se revirtió el fix original (se habían insertado 359 registros `ir_model_data` con `module='binaural_location'` como parche) y se eliminaron en los 3 clientes tras corregir la arquitectura de addons (sección 0). Los scripts SQL de esta sección quedaron **deprecados** — no se necesitan si se sigue la sección 0 correctamente.

**Lección para el protocolo**: cualquier error de `ParseError`/`duplicate key` en un módulo que **no aparece en el pin real del cliente** (`src/custom/<cliente>/integra-addons/<modulo>`) es señal de que se está usando el checkout equivocado, no un problema real del cliente. Verificar SIEMPRE con:
```bash
ls src/custom/<cliente>/integra-addons/<modulo_sospechoso>/__manifest__.py
```
Si no existe, el problema es de arquitectura de addons (sección 0), no del cliente.

---

### Hallazgo #4 — Vistas huérfanas legacy IoT en `l10n_ve_pos_mf` (esperado en clientes CON `l10n_ve_pos_mf` instalado)

**Síntoma**:
```
ParseError: .../pos_config.xml ... Field `iface_fiscal_data_module` does not exist
ParseError: .../pos_payment_method.xml ... El campo "enableb_cross_move" no existe
```

**Causa**: Antes de la migración a Web Serial, `l10n_ve_pos_mf` tenía vistas con campos IoT-específicos (`iface_fiscal_data_module`, `iot_mf` en `pos.session`) que fueron eliminados del código actual, pero cuyos registros `ir.ui.view`/`ir.model.fields` **quedaron huérfanos en la base de datos** (Odoo no borra automáticamente registros de módulos que no se estén actualizando).

Adicionalmente, `enableb_cross_move` es un campo **de otro módulo** (`l10n_ve_pos`, no `l10n_ve_pos_mf`) con el mismo problema de drift — aparece porque ambos módulos tocan el mismo modelo `pos.payment.method`.

**Vistas huérfanas confirmadas** (mismas en Grupo Kam y Solumedica):
- `l10n_ve_pos_mf.pos_config_view_form_inherit` (modelo `pos.config`)
- `l10n_ve_pos_mf.l10n_ve_pos_mf_res_config_settings_view_form_inherit_pos_iot` (modelo `res.config.settings`)

**Fix**:
1. Desactivar manualmente estas 2 vistas ANTES del upgrade (evita el ParseError durante la carga):
   ```sql
   UPDATE ir_ui_view SET active = false
   WHERE id IN (
       SELECT v.id FROM ir_ui_view v
       JOIN ir_model_data d ON d.model='ir.ui.view' AND d.res_id=v.id
       WHERE d.module='l10n_ve_pos_mf'
       AND d.name IN ('pos_config_view_form_inherit', 'l10n_ve_pos_mf_res_config_settings_view_form_inherit_pos_iot')
   );
   ```
2. Incluir `l10n_ve_pos` en el scope de `-u` (soluciona `enableb_cross_move`).
3. Al correr el upgrade, Odoo **borra automáticamente** las vistas/campos huérfanos (se ve en el log: `Deleting ... ir.ui.view`, `Deleting ... ir.model.fields`) — la desactivación manual solo evita que el ParseError bloquee la carga ANTES de llegar a ese punto de limpieza.

**Cómo detectar proactivamente en un cliente nuevo** (antes de correr `-u`):
```sql
SELECT d.module, d.name as xmlid, v.id, v.model
FROM ir_ui_view v
JOIN ir_model_data d ON d.model='ir.ui.view' AND d.res_id=v.id
WHERE d.module IN ('l10n_ve_pos_mf','l10n_ve_iot_mf')
ORDER BY d.module, d.name;
```
Comparar la lista contra los `record id="..."` actuales en `src/odoo-venezuela-17/l10n_ve_pos_mf/views/*.xml` y `l10n_ve_iot_mf/views/*.xml`. Cualquier xmlid en DB que no exista en el código actual es candidato a huérfano.

---

### Hallazgo #5 — Regresión funcional: pérdida de líneas informativas custom (CRÍTICO, ya corregido en el repo)

**Síntoma**: Ningún error visible — falla **silenciosa**. Las líneas informativas personalizadas que un cliente agrega vía override de `check_print_out_invoice()` (ej. "NUMERO DE CONTROL", "REFERENCIA", tasa del día) **no llegan a la impresora fiscal** al imprimir desde Facturación.

**Causa**: En el flujo IoT legacy, el diccionario `res["info"]` devuelto por `check_print_out_invoice()` viajaba completo hacia el IoT Box, donde el SDK Python (`SerialFiscalDriver.py`) lo consumía como líneas `iXX` de encabezado. En el nuevo flujo Web Serial, el navegador reemplaza al IoT Box — pero `toDriverOrder()` en `mf_webserial_service.js` **no mapeaba** `payload.info` a `additional_lines` (quedaba hardcodeado como `[]`).

**Cliente afectado confirmado**: Solumedica (`solumedica_mf/models/account_move.py` sobreescribe `check_print_out_invoice()` agregando `res["info"]`).

**Riesgo para otros clientes**: Cualquier cliente con una customización similar (override de `check_print_out_invoice`/`check_print_out_refund`/`check_print_debit_note` que agregue `res["info"]`) tiene el mismo riesgo. **Revisar proactivamente** los módulos custom de cada cliente por este patrón antes de migrar (ver checklist 6.1).

**Fix aplicado** (ya en el repo, `l10n_ve_iot_mf/static/src/backend/mf_webserial_service.js`):
```javascript
const additionalLines = Array.isArray(payload.info)
    ? payload.info.filter((line) => !!line).map((line) => String(line))
    : [];
// ...
additional_lines: additionalLines,
```

**Cómo detectar en un cliente**: buscar en su repo custom:
```bash
grep -rn 'res\["info"\]\|res\[.info.\]' src/custom/<cliente>/*/models/account_move.py
```
Si aparece, validar en el checklist que esas líneas SÍ se impriman físicamente tras la migración.

---

### Hallazgo #6 — Módulos JS con sintaxis Odoo 14-16 en checkout compartido desactualizado

**Síntoma** (en consola del navegador, no en logs de servidor):
```
Uncaught Error: Dependencies should be defined by an array: function(require){"use strict";...}
    at ModuleLoader.define (point_of_sale.assets_prod.min.js:...)
```

**Causa**: Mismo origen que el Hallazgo #3 (retractado) — usar el checkout compartido de `integra-addons` en vez del submodule pineado del cliente. El checkout compartido (rama `maintenance-17.0.1`) tiene módulos con código JS más viejo (`odoo.define("name", function(require){...})`, sin array de dependencias — sintaxis Odoo 14-16) que Odoo 17 rechaza en tiempo de ejecución en el navegador.

**Módulo confirmado con este problema**: `binaural_pos_last_cost/static/src/js/models.js` (en el checkout compartido). El mismo archivo en el pin real de Dialca **ya tiene la sintaxis correcta** (`["point_of_sale.models","point_of_sale.Registries"]`).

**Fix**: seguir la sección 0 — usar `src/custom/<cliente>/integra-addons` en vez de `src/integra-addons-17`. No requiere tocar código.

**Cómo verificar que el bundle servido tiene la sintaxis correcta** (sin depender del navegador):
```bash
# Dentro del contenedor, vía odoo shell:
docker exec -i odoo-<cliente> odoo shell -d <cliente> --no-http <<'EOF'
bundle = env['ir.qweb']._get_asset_bundle('point_of_sale._assets_pos')
js = bundle.js()
print(js.raw.decode('utf-8', errors='ignore').count('function(require){"use strict"'))
# Cualquier match de este patrón (sin array antes) indica módulo viejo colado
EOF
```

**Nota importante**: el bundle de assets se genera **directamente desde los archivos en disco** cada vez (no depende del estado `installed`/`to upgrade` del módulo en `ir_module_module`). Si cambias el addons path, borra los `ir_attachment` cacheados del bundle afectado para forzar regeneración inmediata:
```sql
DELETE FROM ir_attachment WHERE name LIKE '%point_of_sale.assets%';
```

---

### Hallazgo #7 — `code_fiscal_printer` con valor default sin configurar al instalar `l10n_ve_pos_mf` por primera vez

**Síntoma**: ningún error — silencioso. Todos los `pos.payment.method` quedan con `code_fiscal_printer = '01'` (Efectivo) sin importar su tipo real (transferencia, PDV, crédito, etc.).

**Causa**: el campo tiene `default="01"` en el modelo (`l10n_ve_pos_mf/models/pos_payment_method.py`). Al instalar el módulo por primera vez en un cliente que **nunca** lo tuvo (ej. Dialca, que solo usaba fiscal desde Facturación), Odoo aplica el default a TODOS los métodos de pago existentes, sin distinción.

**Cómo se ve un cliente correctamente configurado** (Grupo Kam y Solumedica, que ya tenían `l10n_ve_pos_mf` en producción antes de esta migración):
```sql
-- Grupo Kam: códigos diversos 00-18, distribuidos según cada método real
-- Solumedica: 01, 07, 10, 13, 16, 22
SELECT code_fiscal_printer, count(*) FROM pos_payment_method GROUP BY code_fiscal_printer;
```

**Cómo se ve un cliente recién instalado sin configurar** (Dialca):
```sql
-- TODOS en '01', sin distinción real
```

**Fix**: **no automatizable** — requiere configuración manual del cliente/consultor:
1. Consultar (vía Fiscalizador → "Medios de Pago (S4)") qué códigos están realmente programados en la impresora física
2. Para cada `pos.payment.method` real (efectivo, tarjetas, transferencias, PDV, etc.), asignar el código correspondiente en Punto de Venta → Configuración → Métodos de Pago
3. **No dejar en `01` por defecto** ningún método que no sea efectivo real — imprimirá el ticket fiscal con el tipo de pago incorrecto

**Cuándo aplica**: SOLO quando `l10n_ve_pos_mf` se instala por primera vez en un cliente (no aplicaba antes en POS, ej. Dialca). Si el cliente ya tenía el módulo en producción (Grupo Kam, Solumedica), su configuración real se preserva intacta en el backup — no se toca.

---

## 4. Otros Hallazgos Menores (no bloqueantes, informativos)

- **Módulos "not installable"**: en los 3 clientes aparecen decenas de módulos `binaural_*` marcados "Unmet dependencies" o "not installable" en el log. Son módulos legacy/deprecados del cliente que **ya estaban así antes de nuestra migración** — no relacionados a lo fiscal. No requieren acción.
- **Vistas inválidas en módulos fuera de scope**: al correr `-u` con una lista acotada de módulos, Odoo emite **warnings** (no errores) tipo `invalid custom view(s) for model X: ... campo Y no existe` para vistas de módulos que NO están en el scope del `-u`. Esto es **normal y no bloquea** — Odoo simplemente omite esa vista específica. Confirmado en Solumedica (payroll, HR, sale.order) sin impacto.
- **`website_track` FK violation** (solo Solumedica, 1 fila): error aislado de datos de analítica web en el dump original, no relacionado a fiscal ni bloqueante para el resto del restore.
- **Permisos de filestore tras comandos `-u root`**: si el upgrade de módulos se corre con `docker exec -u root ...` (necesario para tener permisos de escritura en algunos casos), el directorio `/home/odoo/data` puede quedar con archivos/directorios nuevos propiedad de `root`, causando `PermissionError: [Errno 13] Permission denied` al generar los asset bundles cuando el proceso normal de Odoo (usuario `odoo`) intenta escribir. **Síntoma**: error 500 en `/web/assets/.../web.assets_web.min.js` justo al hacer login. **Fix**: `docker exec -u root odoo-<cliente> chown -R odoo:odoo /home/odoo/data` + `docker restart odoo-<cliente>`. Aplicar preventivamente después de CUALQUIER comando `-u root` sobre un cliente.

---

## 5. Procedimiento de Migración (por cliente)

### 5.1 Preparación

```bash
# Clonar repo del cliente (si no existe)
git clone git@github.com:binaural-dev/<cliente>.git src/custom/<cliente>

# Verificar rama correcta (confirmar contra el nombre del backup)
cd src/custom/<cliente> && git branch -a
git checkout <rama_del_backup>   # ej. release, staging_bs

# Inicializar submodules del PIN REAL del cliente (ver sección 0 — CRÍTICO)
git submodule update --init integra-addons third-party-addons
# NO inicializar 'odoo-venezuela' — usamos src/odoo-venezuela-17 compartido

# Agregar instancia a instances.json apuntando a los submodules del cliente
# (ver sección 0 para el formato exacto de "addons")

./odoo build
./odoo start <cliente>
```

### 5.2 Restaurar Backup

```bash
# Extraer dump del zip de Odoo.sh (formato: dump.sql + filestore/)
unzip -o -p "<ruta_backup>.zip" dump.sql > /tmp/<cliente>_dump.sql

# Crear DB limpia
docker exec -e PGPASSWORD=odoo odoo-<cliente> psql --host host.docker.internal --port 5433 -U odoo -d postgres -c "DROP DATABASE IF EXISTS <cliente>;"
docker exec -e PGPASSWORD=odoo odoo-<cliente> psql --host host.docker.internal --port 5433 -U odoo -d postgres -c "CREATE DATABASE <cliente> OWNER odoo;"

# Copiar y restaurar (copiar al contenedor es más rápido que streaming por exec para dumps grandes)
docker cp /tmp/<cliente>_dump.sql odoo-<cliente>:/tmp/<cliente>_dump.sql
docker exec -e PGPASSWORD=odoo odoo-<cliente> bash -c \
  "psql --host host.docker.internal --port 5433 -U odoo -d <cliente> -f /tmp/<cliente>_dump.sql" \
  > /tmp/<cliente>_restore.log 2>&1

# SIEMPRE verificar errores reales (excluyendo ruido de reintentos)
grep -i "ERROR" /tmp/<cliente>_restore.log
```

⚠️ **Importante**: correr el restore **UNA SOLA VEZ** sobre DB limpia. Si se re-ejecuta sobre una DB ya poblada aparecen falsos "already exists" que no son errores reales.

### 5.3 Ajustar Entorno Local

```bash
docker exec -e PGPASSWORD=odoo odoo-<cliente> psql --host host.docker.internal --port 5433 -U odoo -d <cliente> -c "
UPDATE ir_config_parameter SET value = 'http://localhost:<puerto>' WHERE key = 'web.base.url';
UPDATE res_users SET password = 'admin' WHERE login = 'admin';
"
```

### 5.4 Aplicar Fixes Conocidos (Hallazgo #4)

```bash
./src/odoo-venezuela-17/module-specs/migration-protocol/scripts/apply_known_fixes.sh odoo-<cliente> <cliente>
```

Este script aplica automáticamente la desactivación de vistas huérfanas legacy IoT (Hallazgo #4). El script también incluye pasos para el Hallazgo #3 (retractado) — son no-destructivos e idempotentes si igual se corren, pero **no son necesarios** si ya se siguió la sección 0 correctamente (usar submodule del cliente, no checkout compartido).

### 5.5 Diagnóstico Previo (recomendado)

Antes de correr el upgrade, verificar qué módulos fiscales están instalados y su versión:

```sql
SELECT name, state, latest_version FROM ir_module_module
WHERE name IN ('l10n_ve_iot_mf','l10n_ve_pos_mf','l10n_ve_mf_base','l10n_ve_payment_extension','l10n_ve_pos')
   OR name LIKE '%_mf' OR name LIKE '%_iot%';
```

Esto determina si el cliente usa:
- Solo Facturación (`l10n_ve_iot_mf` instalado, `l10n_ve_pos_mf` no) → caso Dialca
- Facturación + POS (`l10n_ve_pos_mf` también instalado) → caso Grupo Kam
- Facturación + POS + módulo custom propio (`<cliente>_mf`) → caso Solumedica

Buscar módulos custom con lógica fiscal propia (riesgo Hallazgo #5):
```bash
grep -rln "check_print_out_invoice\|check_print_out_refund\|check_print_debit_note" src/custom/<cliente>/*/models/*.py
```

### 5.6 Ejecutar Upgrade de Módulos

**NO usar `-u all`** — dispara decenas de bugs de módulos legacy no relacionados (ver Hallazgo #2 pattern, se multiplica con módulos ajenos). Usar scope acotado:

```bash
docker exec -u root odoo-<cliente> odoo --stop-after-init --http-port=<puerto_libre> -d <cliente> \
    -u l10n_ve_payment_extension,l10n_ve_pos,l10n_ve_iot_mf,l10n_ve_pos_mf,l10n_ve_mf_base
```

Si el cliente tiene módulo(s) custom de MF propio (ej. `solumedica_mf`), agregarlos al final del `-u`.

**Si aparece un nuevo ParseError** (campo/vista no existe):
1. Identificar el módulo dueño real del contenido (puede no ser el que aparece en el traceback — buscar en `ir_ui_view`/`ir_model_data` por contenido, ver Hallazgo #4).
2. Si es un módulo compartido (`binaural_*`, `l10n_ve_*`), agregarlo al `-u` para que se refresque.
3. Si es una vista genuinamente huérfana (xmlid ya no existe en código actual), desactivarla (`active=false`) antes de reintentar.

Confirmar en el log:
```
odoo.modules.registry: Registry loaded in X.XXXs
```
sin `CRITICAL`/`Failed to load registry` después de esa línea.

### 5.7 Reiniciar y Verificar

```bash
docker restart odoo-<cliente>
sleep 8
curl -s -o /dev/null -w "HTTP: %{http_code}\n" -L http://localhost:<puerto>/web/login
# Esperado: 200
```

---

## 6. Checklist de Validación

### 6.1 Pre-Migración (análisis de riesgo por cliente)

- [ ] ¿Qué módulos fiscales tiene instalados? (Facturación / POS / ambos / módulo custom propio)
- [ ] ¿Tiene módulo custom que sobreescriba `check_print_out_invoice/refund/debit_note`? → riesgo Hallazgo #5, revisar que use `res["info"]` o estructura equivalente
- [ ] ¿Tiene vistas custom sobre `pos.config`, `pos.payment.method`, `account.move`? → riesgo de colisión con limpieza de huérfanas
- [ ] Versión actual de `l10n_ve_iot_mf`/`l10n_ve_pos_mf` en el backup (para saber si el jump de versión activará el post-migration)
- [ ] Si `l10n_ve_pos_mf` **se va a instalar por primera vez** (cliente que antes solo usaba fiscal en Facturación): planificar configuración manual de `code_fiscal_printer` por método de pago post-instalación (Hallazgo #7) — NO queda listo para producción solo con la instalación

### 6.2 Técnica (post-upgrade, vía SQL/logs — sin UI)

- [ ] `Registry loaded` sin `CRITICAL` en el log de upgrade
- [ ] `mf_flag_21` poblado en `res_company` para todas las compañías:
  ```sql
  SELECT id, name, mf_flag_21 FROM res_company;
  ```
- [ ] Log de upgrade contiene la línea de post-migration ejecutada:
  ```
  Running upgrade [17.0.0.3.0>] post-migration
  ```
- [ ] `l10n_ve_mf_base` quedó `installed` (auto-instalado como dependencia)
- [ ] Ningún módulo en estado colgado:
  ```sql
  SELECT name, state FROM ir_module_module WHERE state IN ('to upgrade','to install','to remove');
  ```
- [ ] HTTP 200 en `/web/login`

### 6.3 Funcional (interactiva en navegador — requiere Chrome/Edge y hardware conectado)

**Facturación/Contabilidad**:
- [ ] Sección "Fiscal Machine" única (no duplicada) en pestaña "Otra información" de facturas
- [ ] Botones de impresión MF visibles en el header de facturas validadas
- [ ] Fiscalizador accesible (`?debug=1` → bug icon → "Fiscalizador MF")
- [ ] Systray muestra icono de conexión (gris = desconectado)
- [ ] Conectar impresora vía Fiscalizador → botón "Medios de Pago (S4)" lista códigos programados
- [ ] Imprimir factura de prueba → número fiscal se puebla, `mf_serial`/`mf_reportz` correctos
- [ ] **Si el cliente tiene líneas informativas custom** (Hallazgo #5): confirmar que aparecen físicamente en el ticket impreso
- [ ] Reimpresión de factura ya impresa funciona
- [ ] Nota de Crédito y Nota de Débito imprimen correctamente
- [ ] Wizard "Reportes Maquina Fiscal": Reporte X, Reporte Z (con confirmación), impresión por rango de fecha, reimpresión por fecha

**POS** (solo si `l10n_ve_pos_mf` está instalado):
- [ ] Conectar impresora fiscal desde POS
- [ ] Pedido con un solo método de pago imprime correctamente
- [ ] Pedido con **múltiples métodos de pago** imprime correctamente (cierre `1<método_mayor_monto>` + `2XX` de los demás)
- [ ] Nota de crédito desde POS
- [ ] Reporte Z desde POS
- [ ] Desconexión de red backend → pedido se guarda en buffer offline → reconexión → sincroniza

### 6.4 Regresión (nada debe romperse)

- [ ] Crear factura normal sin impresión fiscal (modo "free") funciona
- [ ] Envío de factura por email genera PDF correctamente
- [ ] Libro de Ventas (IVA) sin errores
- [ ] Módulos custom del cliente cargan sin warnings nuevos de vistas inválidas

---

## 7. Assets Reutilizables

Ubicados en `src/odoo-venezuela-17/module-specs/migration-protocol/scripts/`:

| Archivo | Propósito |
|---|---|
| `apply_known_fixes.sh` | Aplica la desactivación de vistas huérfanas legacy IoT (Hallazgo #4). Incluye pasos del Hallazgo #3 retractado por compatibilidad, pero no son necesarios si se sigue la sección 0. |
| `fix_country_state_xmlids.sql` | **Deprecado** (Hallazgo #3 retractado) — conservado por si algún cliente SÍ tiene `binaural_location` real en su pin (verificar primero, sección 3 Hallazgo #3) |
| `fix_municipality_xmlids.sql` | **Deprecado**, mismo criterio que arriba |
| `generate_repair_scripts.py` | Regenera los 2 SQL anteriores si hiciera falta para un caso específico |

---

## 8. Estado de Clientes (13 total)

> **Regla de arquitectura (Sección 0):** los clientes que tienen submodule `odoo-venezuela` pineado en su repo **deben ignorarlo** durante la migración. Se usa en su lugar el checkout compartido `src/odoo-venezuela-17` (rama `feature/pos-mf-web-serial-api`).

### 8.1 Clientes Migrados (3/13)

| # | Cliente | Rama | `integra-addons` | `third-party-addons` | `odoo-venezuela` (legacy pin) | Custom MF | Estado |
|---|---|---|---|---|---|---|---|
| 1 | **Dialca** | `staging_bs` | [66f5d975](https://github.com/binaural-dev/integra-addons/commit/66f5d975) | [9b1bb1b4](https://github.com/binaural-dev/third-party-addons/commit/9b1bb1b4) | [08f84773](https://github.com/binaural-dev/odoo-venezuela/commit/08f84773) | `dialca_iot` (uninstalled) | ✅ Migrado, `l10n_ve_pos_mf` recién instalado — **pendiente configurar `code_fiscal_printer` por método de pago (Hallazgo #7)** |
| 2 | **Grupo Kam 2** | `release` | [a4f7274e](https://github.com/binaural-dev/integra-addons/commit/a4f7274e) | [d2bfb706](https://github.com/binaural-dev/third-party-addons/commit/d2bfb706) | [94809746](https://github.com/binaural-dev/odoo-venezuela/commit/94809746) | — | ✅ Migrado, `code_fiscal_printer` real preservado |
| 3 | **Solumedica** | `release` | [8532567e](https://github.com/binaural-dev/integra-addons/commit/8532567e) | [04b060bb](https://github.com/binaural-dev/third-party-addons/commit/04b060bb) | [697e7d8a](https://github.com/binaural-dev/odoo-venezuela/commit/697e7d8a) | `solumedica_mf` | ✅ Migrado (fix regresión Hallazgo #5), `code_fiscal_printer` real preservado |

### 8.2 Clientes Pendientes (10/13)

| # | Cliente | Rama | `integra-addons` | `third-party-addons` | `odoo-venezuela` (legacy pin) | ¿Tiene pin `odoo-venezuela`? |
|---|---|---|---|---|---|---|
| 4 | Armorpets | `release` | [ae32f83e](https://github.com/binaural-dev/integra-addons/commit/ae32f83e) | [66e6de89](https://github.com/binaural-dev/third-party-addons/commit/66e6de89) | [f0ad4e25](https://github.com/binaural-dev/odoo-venezuela/commit/f0ad4e25) | Sí — requiere Sección 0 |
| 5 | Asia Center | `release` | [83975ad9](https://github.com/binaural-dev/integra-addons/commit/83975ad9) | [d81d22b9](https://github.com/binaural-dev/third-party-addons/commit/d81d22b9) | — | No |
| 6 | Bisuteria R y R | `release` | [e2b66a44](https://github.com/binaural-dev/integra-addons/commit/e2b66a44) | [deee40d8](https://github.com/binaural-dev/third-party-addons/commit/deee40d8) | — | No |
| 7 | Bisuteria 888 | `release` | [9106e8b4](https://github.com/binaural-dev/integra-addons/commit/9106e8b4) | [ef3979c7](https://github.com/binaural-dev/third-party-addons/commit/ef3979c7) | — | No |
| 8 | Dicosmo | `release` | [b691ddfc](https://github.com/binaural-dev/integra-addons/commit/b691ddfc) | [2c6d0273](https://github.com/binaural-dev/third-party-addons/commit/2c6d0273) | — | No |
| 9 | Higea | `release` | [2e57a291](https://github.com/binaural-dev/integra-addons/commit/2e57a291) | [b7c86016](https://github.com/binaural-dev/third-party-addons/commit/b7c86016) | — | No |
| 10 | Lanpro System | `release` | [f9a2f7a5](https://github.com/binaural-dev/integra-addons/commit/f9a2f7a5) | [04b060bb](https://github.com/binaural-dev/third-party-addons/commit/04b060bb) | — | No |
| 11 | RM Valencia | `release` | [57ebdc7e](https://github.com/binaural-dev/integra-addons/commit/57ebdc7e) | [5e2737c8](https://github.com/binaural-dev/third-party-addons/commit/5e2737c8) | — | No |
| 12 | Sankey | `release` | [bdef398a](https://github.com/binaural-dev/integra-addons/commit/bdef398a) | [b7c86016](https://github.com/binaural-dev/third-party-addons/commit/b7c86016) | — | No |
| 13 | Uvet | `release` | [71ecc46f](https://github.com/binaural-dev/integra-addons/commit/71ecc46f) | [723dd1d4](https://github.com/binaural-dev/third-party-addons/commit/723dd1d4) | [d292190c](https://github.com/binaural-dev/odoo-venezuela/commit/d292190c) | Sí — requiere Sección 0 |

### 8.3 Observaciones Generales

*   **5 de 13 clientes** tienen submodule `odoo-venezuela` pineado: Dialca, Grupo Kam 2, Solumedica, Amorpets, Uvet. Para estos, la **Sección 0 del protocolo es obligatoria**: NO inicializar ese submodule y usar `src/odoo-venezuela-17` compartido en su lugar.
*   **8 de 13 clientes** no tienen submodule `odoo-venezuela`: son más simples de migrar porque no hay riesgo de colisión de módulos entre el pin viejo y el código nuevo.
*   Todos los clientes pendientes usan la rama `release` como default — consistente para despliegue en Odoo.sh.
*   Higea y Sankey comparten el mismo commit de `third-party-addons` (`b7c86016`), igual que Grupo Kam 2.
*   Solumedica y Lanpro System comparten el mismo commit de `third-party-addons` (`04b060bb`).

Recomendación para cada uno de los 10 pendientes:
1. Clonar el repo del cliente (`git clone git@github.com:binaural-dev/<cliente>.git src/custom/<cliente>`)
2. Hacer checkout de su rama `release`
3. Inicializar SOLO `integra-addons` y `third-party-addons` (`git submodule update --init integra-addons third-party-addons`). Si tiene `odoo-venezuela`, NO inicializarlo.
4. Ejecutar diagnóstico de la sección 5.5 (módulos custom fiscales propios) para anticipar riesgos tipo Hallazgo #5
5. Si el cliente tiene submodule `odoo-venezuela`, verificar que el `instances.json` NO lo incluya en `addons` (usar `src/odoo-venezuela-17` en su lugar, ver Sección 0)
