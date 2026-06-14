/** @odoo-module */

import { registry } from "@web/core/registry";
import { FiscalProtocol } from "../core/FiscalProtocol";
import { StatusParser } from "../core/StatusParser";
import { TfhkaDriver } from "../drivers/TfhkaDriver";
import { MockSerialConnection } from "./MockSerialConnection";

/**
 * Suite de Tests para el Driver de Máquina Fiscal TFHKA
 * 
 * Tests implementados:
 * 1. Cálculo correcto de LRC (XOR checksum)
 * 2. Parsing de tramas con STX/ETX/LRC
 * 3. Reintentos automáticos ante NAK
 * 4. Detección de error de papel (STS2 bit 6)
 * 5. Detección de memoria fiscal llena (STS1 bit 4)
 * 6. Factura completa exitosa
 */

// ============ TESTS DE PROTOCOLO (FiscalProtocol) ============

QUnit.module("TFHKA - FiscalProtocol");

QUnit.test("Cálculo correcto de LRC (XOR checksum)", (assert) => {
    // Test 1: Comando simple "I0X" (Reporte X)
    const frame1 = FiscalProtocol.buildFrame("I0X");
    
    // La trama debe ser: STX + 'I' + '0' + 'X' + ETX + LRC
    assert.strictEqual(frame1[0], 0x02, "Inicia con STX (0x02)");
    assert.strictEqual(frame1[1], 0x49, "Contiene 'I' (0x49)");
    assert.strictEqual(frame1[2], 0x30, "Contiene '0' (0x30)");
    assert.strictEqual(frame1[3], 0x58, "Contiene 'X' (0x58)");
    assert.strictEqual(frame1[4], 0x03, "Contiene ETX (0x03)");
    
    // Calcular LRC manualmente: 0x02 ^ 0x49 ^ 0x30 ^ 0x58 ^ 0x03
    const expectedLRC1 = 0x02 ^ 0x49 ^ 0x30 ^ 0x58 ^ 0x03;
    assert.strictEqual(frame1[5], expectedLRC1, `LRC correcto: 0x${expectedLRC1.toString(16)}`);
    
    // Test 2: Comando con RIF "@J123456789"
    const frame2 = FiscalProtocol.buildFrame("@J123456789");
    const dataBytes = frame2.slice(0, frame2.length - 1);
    const calculatedLRC = FiscalProtocol.calculateLRC(dataBytes);
    assert.strictEqual(frame2[frame2.length - 1], calculatedLRC, "LRC correcto para comando con RIF");
});

QUnit.test("Parsing de respuesta válida con STX/ETX/LRC", (assert) => {
    // Construir una respuesta simulada: STX + "OK" + ETX + LRC
    const encoder = new TextEncoder();
    const data = encoder.encode("OK");
    
    const frameWithoutLRC = new Uint8Array(1 + data.length + 1);
    frameWithoutLRC[0] = FiscalProtocol.STX;
    frameWithoutLRC.set(data, 1);
    frameWithoutLRC[frameWithoutLRC.length - 1] = FiscalProtocol.ETX;
    
    const lrc = FiscalProtocol.calculateLRC(frameWithoutLRC);
    const frame = new Uint8Array(frameWithoutLRC.length + 1);
    frame.set(frameWithoutLRC, 0);
    frame[frame.length - 1] = lrc;
    
    // Parsear
    const parsed = FiscalProtocol.parseResponse(frame);
    
    assert.ok(parsed.valid, "Respuesta marcada como válida");
    assert.strictEqual(parsed.data, "OK", "Data extraída correctamente");
    assert.strictEqual(parsed.error, "", "Sin errores");
});

QUnit.test("Parsing de respuesta con LRC inválido", (assert) => {
    // Construir trama con LRC incorrecto
    const frame = new Uint8Array([
        FiscalProtocol.STX,
        0x4F, // 'O'
        0x4B, // 'K'
        FiscalProtocol.ETX,
        0xFF  // LRC inválido (debería ser otro valor)
    ]);
    
    const parsed = FiscalProtocol.parseResponse(frame);
    
    assert.notOk(parsed.valid, "Respuesta marcada como inválida");
    assert.ok(parsed.error.includes("LRC inválido"), "Error de LRC detectado");
});

QUnit.test("Detección de ACK y NAK", (assert) => {
    const ackFrame = new Uint8Array([FiscalProtocol.ACK]);
    const nakFrame = new Uint8Array([FiscalProtocol.NAK]);
    const otherFrame = new Uint8Array([0x42]); // Cualquier otro byte
    
    assert.ok(FiscalProtocol.isACK(ackFrame), "ACK detectado correctamente");
    assert.notOk(FiscalProtocol.isACK(nakFrame), "NAK no es ACK");
    
    assert.ok(FiscalProtocol.isNAK(nakFrame), "NAK detectado correctamente");
    assert.notOk(FiscalProtocol.isNAK(ackFrame), "ACK no es NAK");
    assert.notOk(FiscalProtocol.isNAK(otherFrame), "Otro byte no es NAK");
});

// ============ TESTS DE STATUS PARSER ============

QUnit.module("TFHKA - StatusParser");

QUnit.test("Parser de STS1 (Estado de la impresora)", (assert) => {
    // STS1 = 0x64 (0110 0100)
    // Bit 2 (Modo Fiscal) = 1
    // Bit 5 (Buffer Lleno) = 1
    const sts1 = 0x64;
    const state = StatusParser.parseSTS1(sts1);
    
    assert.ok(state.fiscalMode, "Modo Fiscal detectado");
    assert.ok(state.bufferFull, "Buffer lleno detectado");
    assert.notOk(state.fiscalMemoryFull, "Memoria fiscal no llena");
    assert.ok(state.isFiscalReady, "Estado: Fiscal en espera");
});

QUnit.test("Parser de STS2 (Errores de la impresora)", (assert) => {
    // STS2 = 0x48 (0100 1000)
    // Bit 3 (Gaveta) = 1
    const sts2 = 0x48;
    const errors = StatusParser.parseSTS2(sts2);
    
    assert.ok(errors.drawerError, "Error de gaveta detectado");
    assert.notOk(errors.paperError, "Sin error de papel");
    assert.notOk(errors.criticalError, "Sin error crítico");
    assert.ok(errors.hasDrawerIssue, "Helper: Gaveta con problema");
});

QUnit.test("Detección de error de papel (STS2 bit 6)", (assert) => {
    // STS2 = 0x41 (Sin papel - bit 6 en alto)
    const sts2 = 0x41;
    const errors = StatusParser.parseSTS2(sts2);
    
    assert.ok(errors.paperError, "Error de papel detectado");
    assert.ok(errors.hasPaperIssue, "Helper: Problema de papel");
    assert.notOk(StatusParser.isOperational(0x60, sts2), "Impresora NO operativa por falta de papel");
});

QUnit.test("Detección de memoria fiscal llena (STS1 bit 4)", (assert) => {
    // STS1 = 0x14 (Bit 4 en alto - memoria llena)
    const sts1 = 0x14;
    const state = StatusParser.parseSTS1(sts1);
    
    assert.ok(state.fiscalMemoryFull, "Memoria fiscal llena detectada");
    assert.notOk(StatusParser.isOperational(sts1, 0x40), "Impresora NO operativa por memoria llena");
});

QUnit.test("Estado operativo sin errores", (assert) => {
    // STS1 = 0x60 (Fiscal en espera), STS2 = 0x40 (Sin errores)
    const sts1 = 0x60;
    const sts2 = 0x40;
    
    assert.ok(StatusParser.isOperational(sts1, sts2), "Impresora operativa");
    assert.notOk(StatusParser.hasErrors(sts2), "Sin errores activos");
    
    const statusText = StatusParser.getStatusText(sts1, sts2);
    assert.ok(statusText.includes("Lista") || statusText.includes("Operativa"), "Texto de status correcto");
});

// ============ TESTS DE DRIVER (TfhkaDriver con Mock) ============

QUnit.module("TFHKA - TfhkaDriver (con MockSerialConnection)");

QUnit.test("Conexión exitosa y lectura de status", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    
    // Configurar respuesta de status simulada (STS1=0x60, STS2=0x40)
    driver.connection.setNextResponse("STATUS");
    
    const connected = await driver.connect();
    assert.ok(connected, "Driver conectado exitosamente");
    
    const status = await driver.getStatus();
    assert.ok(status, "Status recibido");
    assert.ok(status.raw, "Status contiene datos raw");
});

QUnit.test("Reintentos automáticos ante NAK (3 intentos)", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    driver.retryDelay = 10; // Reducir delay para testing
    
    await driver.connection.requestPort();
    driver.isConnected = true;
    
    // Configurar secuencia: NAK, NAK, ACK (éxito al 3er intento)
    driver.connection.setResponseSequence(["NAK", "NAK", "ACK"]);
    
    const result = await driver.sendCommand("I0X");
    
    assert.ok(result.success, "Comando exitoso después de reintentos");
    assert.strictEqual(result.data, "ACK", "Respuesta correcta recibida");
    
    // Verificar que se enviaron 3 comandos
    const commandsHistory = driver.connection.getSentCommands();
    assert.strictEqual(commandsHistory.length, 3, "Se enviaron exactamente 3 comandos");
});

QUnit.test("Fallo después de agotar reintentos (3 NAK seguidos)", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    driver.retryDelay = 10;
    
    await driver.connection.requestPort();
    driver.isConnected = true;
    
    // Configurar 3 NAK seguidos (sin ACK)
    driver.connection.setResponseSequence(["NAK", "NAK", "NAK"]);
    
    const result = await driver.sendCommand("I0X");
    
    assert.notOk(result.success, "Comando falló después de reintentos");
    assert.ok(result.error.includes("reintentos"), "Error indica reintentos agotados");
});

QUnit.test("Apertura de gaveta (comando '0')", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    
    await driver.connection.requestPort();
    driver.isConnected = true;
    
    driver.connection.setNextResponse("ACK");
    
    const result = await driver.openDrawer();
    
    assert.ok(result.success, "Gaveta abierta exitosamente");
    
    // Verificar que se envió el comando correcto
    const lastCommand = driver.connection.getLastCommand();
    assert.ok(lastCommand.text.includes("0"), "Comando '0' enviado");
});

QUnit.test("Impresión de Reporte X (comando 'I0X')", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    
    await driver.connection.requestPort();
    driver.isConnected = true;
    
    driver.connection.setNextResponse("ACK");
    
    const result = await driver.printReportX();
    
    assert.ok(result.success, "Reporte X impreso exitosamente");
    assert.ok(driver.connection.wasCommandSent("I0X"), "Comando 'I0X' enviado");
});

QUnit.test("Impresión de Reporte Z (comando 'I0Z')", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    
    await driver.connection.requestPort();
    driver.isConnected = true;
    
    driver.connection.setNextResponse("ACK");
    
    const result = await driver.printReportZ();
    
    assert.ok(result.success, "Reporte Z impreso exitosamente");
    assert.ok(driver.connection.wasCommandSent("I0Z"), "Comando 'I0Z' enviado");
});

QUnit.test("Factura completa exitosa (flujo completo)", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    
    await driver.connection.requestPort();
    driver.isConnected = true;
    
    // Simular orden completa
    const mockOrder = {
        partner: {
            vat: "J123456789",
            name: "EMPRESA TEST"
        },
        lines: [
            {
                product_id: { display_name: "Producto 1" },
                qty: 2,
                price_unit: 100.50
            },
            {
                product_id: { display_name: "Producto 2" },
                qty: 1,
                price_unit: 50.00
            }
        ],
        payment_ids: [
            { payment_method_id: { type: "cash" } }
        ],
        total_discount: 0
    };
    
    // Configurar respuestas simuladas (ACK para cada comando)
    const expectedCommands = 5; // RIF, Nombre, Producto1, Producto2, Totalización
    for (let i = 0; i < expectedCommands; i++) {
        driver.connection.setNextResponse("ACK");
    }
    
    // Configurar respuesta de status para obtener número de factura
    driver.connection.setNextResponse("STATUS");
    
    const result = await driver.printInvoice(mockOrder);
    
    assert.ok(result.success, "Factura impresa exitosamente");
    
    // Verificar que se enviaron todos los comandos necesarios
    const history = driver.connection.getSentCommands();
    assert.ok(history.length >= 5, `Se enviaron ${history.length} comandos (esperados: ≥5)`);
    
    // Verificar que se envió el RIF
    assert.ok(driver.connection.wasCommandSent("@J123456789"), "RIF enviado correctamente");
    
    // Verificar que se envió el nombre
    assert.ok(driver.connection.wasCommandSent("A"), "Nombre enviado");
    
    // Verificar que se envió el comando de totalización ('1')
    assert.ok(driver.connection.wasCommandSent("1"), "Totalización enviada");
});

QUnit.test("Error de impresión detectado durante factura (debe cancelar)", async (assert) => {
    const driver = new TfhkaDriver();
    driver.connection = new MockSerialConnection();
    
    await driver.connection.requestPort();
    driver.isConnected = true;
    
    const mockOrder = {
        partner: { vat: "J123456789", name: "TEST" },
        lines: [
            { product_id: { display_name: "Producto" }, qty: 1, price_unit: 100 }
        ],
        payment_ids: [{ payment_method_id: { type: "cash" } }],
        total_discount: 0
    };
    
    // Simular error en el segundo comando (nombre)
    driver.connection.setResponseSequence(["ACK", "NAK", "NAK", "NAK"]);
    
    const result = await driver.printInvoice(mockOrder);
    
    assert.notOk(result.success, "Factura falló correctamente");
    assert.ok(result.error.length > 0, "Error reportado");
});

// Registrar tests en el registry de Odoo
registry.category("web_tour.tours").add("tfhka_driver_tests", {
    test: true,
    url: "/web",
    steps: () => [],
});
