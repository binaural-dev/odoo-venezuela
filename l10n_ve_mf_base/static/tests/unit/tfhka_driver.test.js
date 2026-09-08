/** @odoo-module */

import { describe, expect, test } from "@odoo/hoot";
import { FiscalProtocol } from "@l10n_ve_mf_base/core/FiscalProtocol";
import { StatusParser } from "@l10n_ve_mf_base/core/StatusParser";
import { TfhkaDriver } from "@l10n_ve_mf_base/drivers/TfhkaDriver";
import { MockSerialConnection } from "./MockSerialConnection";

function buildS1Payload({
    lastInvoiceNumber = 0,
    lastNCNumber = 0,
    dailyClosureCounter = 0,
    serialMachine = "Z1F0000000",
    rif = "J123456789",
}) {
    const fields = [
        "01",
        "000000000000",
        String(lastInvoiceNumber).padStart(8, "0"),
        "00000001",
        "00000000",
        "00000000",
        String(dailyClosureCounter),
        "00000000",
        rif,
        serialMachine,
        "120000",
        "200626",
        String(lastNCNumber).padStart(8, "0"),
        "00000001",
    ];

    return `S1${fields.join("\n")}`;
}

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

describe("TFHKA - FiscalProtocol", () => {
    test("Cálculo correcto de LRC (XOR checksum)", () => {
        // Test 1: Comando simple "I0X" (Reporte X)
        const frame1 = FiscalProtocol.buildFrame("I0X");

        // La trama debe ser: STX + 'I' + '0' + 'X' + ETX + LRC
        expect(frame1[0]).toBe(0x02); // Inicia con STX (0x02)
        expect(frame1[1]).toBe(0x49); // Contiene 'I' (0x49)
        expect(frame1[2]).toBe(0x30); // Contiene '0' (0x30)
        expect(frame1[3]).toBe(0x58); // Contiene 'X' (0x58)
        expect(frame1[4]).toBe(0x03); // Contiene ETX (0x03)

        // Calcular LRC manualmente: 0x49 ^ 0x30 ^ 0x58 ^ 0x03 (sin STX)
        const expectedLRC1 = 0x49 ^ 0x30 ^ 0x58 ^ 0x03;
        expect(frame1[5]).toBe(expectedLRC1); // LRC correcto

        // Test 2: Comando con RIF "@J123456789"
        const frame2 = FiscalProtocol.buildFrame("@J123456789");
        const dataBytes = frame2.slice(1, frame2.length - 1);
        const calculatedLRC = FiscalProtocol.calculateLRC(dataBytes);
        expect(frame2[frame2.length - 1]).toBe(calculatedLRC); // LRC correcto para comando con RIF
    });

    test("Parsing de respuesta válida con STX/ETX/LRC", () => {
        // Construir una respuesta simulada: STX + "OK" + ETX + LRC
        const encoder = new TextEncoder();
        const data = encoder.encode("OK");

        const frameWithoutLRC = new Uint8Array(1 + data.length + 1);
        frameWithoutLRC[0] = FiscalProtocol.STX;
        frameWithoutLRC.set(data, 1);
        frameWithoutLRC[frameWithoutLRC.length - 1] = FiscalProtocol.ETX;

        const lrc = FiscalProtocol.calculateLRC(frameWithoutLRC.slice(1));
        const frame = new Uint8Array(frameWithoutLRC.length + 1);
        frame.set(frameWithoutLRC, 0);
        frame[frame.length - 1] = lrc;

        // Parsear
        const parsed = FiscalProtocol.parseResponse(frame);

        expect(Boolean(parsed.valid)).toBe(true); // Respuesta marcada como válida
        expect(parsed.data).toBe("OK"); // Data extraída correctamente
        expect(parsed.error).toBe(""); // Sin errores
    });

    test("Parsing de respuesta con LRC inválido", () => {
        // Construir trama con LRC incorrecto
        const frame = new Uint8Array([
            FiscalProtocol.STX,
            0x4F, // 'O'
            0x4B, // 'K'
            FiscalProtocol.ETX,
            0xFF  // LRC inválido (debería ser otro valor)
        ]);

        const parsed = FiscalProtocol.parseResponse(frame);

        expect(Boolean(parsed.valid)).toBe(false); // Respuesta marcada como inválida
        expect(Boolean(parsed.error.includes("LRC inválido"))).toBe(true); // Error de LRC detectado
    });

    test("Detección de ACK y NAK", () => {
        const ackFrame = new Uint8Array([FiscalProtocol.ACK]);
        const nakFrame = new Uint8Array([FiscalProtocol.NAK]);
        const otherFrame = new Uint8Array([0x42]); // Cualquier otro byte

        expect(Boolean(FiscalProtocol.isACK(ackFrame))).toBe(true); // ACK detectado correctamente
        expect(Boolean(FiscalProtocol.isACK(nakFrame))).toBe(false); // NAK no es ACK

        expect(Boolean(FiscalProtocol.isNAK(nakFrame))).toBe(true); // NAK detectado correctamente
        expect(Boolean(FiscalProtocol.isNAK(ackFrame))).toBe(false); // ACK no es NAK
        expect(Boolean(FiscalProtocol.isNAK(otherFrame))).toBe(false); // Otro byte no es NAK
    });
});

// ============ TESTS DE STATUS PARSER ============

describe("TFHKA - StatusParser", () => {
    test("Parser de STS1 (Estado de la impresora)", () => {
        // STS1 = 0x64 (0110 0100)
        // Bit 2 (Modo Fiscal) = 1
        // Bit 5 (Buffer Lleno) = 1
        const sts1 = 0x64;
        const state = StatusParser.parseSTS1(sts1);

        expect(Boolean(state.fiscalMode)).toBe(true); // Modo Fiscal detectado
        expect(Boolean(state.bufferFull)).toBe(true); // Buffer lleno detectado
        expect(Boolean(state.fiscalMemoryFull)).toBe(false); // Memoria fiscal no llena
        expect(Boolean(state.isFiscalReady)).toBe(true); // Estado: Fiscal en espera
    });

    test("Parser de STS2 (Errores de la impresora)", () => {
        // STS2 = 0x48 (0100 1000)
        // Bit 3 (Gaveta) = 1
        const sts2 = 0x48;
        const errors = StatusParser.parseSTS2(sts2);

        expect(Boolean(errors.drawerError)).toBe(true); // Error de gaveta detectado
        expect(Boolean(errors.paperError)).toBe(false); // Sin error de papel
        expect(Boolean(errors.criticalError)).toBe(false); // Sin error crítico
        expect(Boolean(errors.hasDrawerIssue)).toBe(true); // Helper: Gaveta con problema
    });

    test("Detección de error de papel (STS2 bit 6)", () => {
        // STS2 = 0x41 (Sin papel - bit 6 en alto)
        const sts2 = 0x41;
        const errors = StatusParser.parseSTS2(sts2);

        expect(Boolean(errors.paperError)).toBe(true); // Error de papel detectado
        expect(Boolean(errors.hasPaperIssue)).toBe(true); // Helper: Problema de papel
        expect(Boolean(StatusParser.isOperational(0x60, sts2))).toBe(false); // Impresora NO operativa por falta de papel
    });

    test("Detección de memoria fiscal llena (STS1 bit 4)", () => {
        // STS1 = 0x14 (Bit 4 en alto - memoria llena)
        const sts1 = 0x14;
        const state = StatusParser.parseSTS1(sts1);

        expect(Boolean(state.fiscalMemoryFull)).toBe(true); // Memoria fiscal llena detectada
        expect(Boolean(StatusParser.isOperational(sts1, 0x40))).toBe(false); // Impresora NO operativa por memoria llena
    });

    test("Estado operativo sin errores", () => {
        // STS1 = 0x60 (Fiscal en espera), STS2 = 0x40 (Sin errores)
        const sts1 = 0x60;
        const sts2 = 0x40;

        expect(Boolean(StatusParser.isOperational(sts1, sts2))).toBe(true); // Impresora operativa
        expect(Boolean(StatusParser.hasErrors(sts2))).toBe(false); // Sin errores activos

        const statusText = StatusParser.getStatusText(sts1, sts2);
        expect(Boolean(typeof statusText === "string" && statusText.length > 0)).toBe(true); // Texto de status correcto
    });
});

// ============ TESTS DE DRIVER (TfhkaDriver con Mock) ============

describe("TFHKA - TfhkaDriver (con MockSerialConnection)", () => {
    test("Conexión exitosa y lectura de status", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();

        // Configurar respuesta de status simulada (STS1=0x60, STS2=0x40)
        driver.connection.setNextResponse("STATUS");

        const connected = await driver.connect();
        expect(Boolean(connected)).toBe(true); // Driver conectado exitosamente

        const status = await driver.getStatus();
        expect(Boolean(status)).toBe(true); // Status recibido
        expect(Boolean(status.raw)).toBe(true); // Status contiene datos raw
    });

    test("Reintentos automáticos ante NAK (3 intentos)", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();
        driver.retryDelay = 10; // Reducir delay para testing

        await driver.connection.requestPort();
        driver.isConnected = true;

        // Configurar secuencia: NAK, NAK, ACK (éxito al 3er intento)
        driver.connection.setResponseSequence(["NAK", "NAK", "ACK"]);

        const result = await driver.sendCommand("I0X");

        expect(Boolean(result.success)).toBe(true); // Comando exitoso después de reintentos
        expect(result.data).toBe("ACK"); // Respuesta correcta recibida

        // Verificar que se enviaron 3 comandos
        const commandsHistory = driver.connection
            .getSentCommands()
            .filter((cmd) => !(cmd.raw?.length === 1 && cmd.raw[0] === FiscalProtocol.ENQ));
        expect(commandsHistory.length).toBe(3); // Se enviaron exactamente 3 comandos fiscales
    });

    test("Fallo después de agotar reintentos (3 NAK seguidos)", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();
        driver.retryDelay = 10;

        await driver.connection.requestPort();
        driver.isConnected = true;

        // Configurar 3 NAK seguidos (sin ACK)
        driver.connection.setResponseSequence(["NAK", "NAK", "NAK"]);

        const result = await driver.sendCommand("I0X");

        expect(Boolean(result.success)).toBe(false); // Comando falló después de reintentos
        expect(Boolean(result.error.includes("reintentos"))).toBe(true); // Error indica reintentos agotados
    });

    test("Apertura de gaveta (comando '0')", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();

        await driver.connection.requestPort();
        driver.isConnected = true;

        driver.connection.setNextResponse("ACK");

        const result = await driver.openDrawer();

        expect(Boolean(result.success)).toBe(true); // Gaveta abierta exitosamente

        // Verificar que se envió el comando correcto
        const lastCommand = driver.connection.getLastCommand();
        expect(Boolean(lastCommand.text.includes("0"))).toBe(true); // Comando '0' enviado
    });

    test("Impresión de Reporte X (comando 'I0X')", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();

        await driver.connection.requestPort();
        driver.isConnected = true;

        driver.connection.setNextResponse("ACK");

        const result = await driver.printReportX();

        expect(Boolean(result.success)).toBe(true); // Reporte X impreso exitosamente
        expect(Boolean(driver.connection.wasCommandSent("I0X"))).toBe(true); // Comando 'I0X' enviado
    });

    test("Impresión de Reporte Z (comando 'I0Z')", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();

        await driver.connection.requestPort();
        driver.isConnected = true;

        driver.connection.setNextResponse("ACK");

        const result = await driver.printReportZ();

        expect(Boolean(result.success)).toBe(true); // Reporte Z impreso exitosamente
        expect(Boolean(driver.connection.wasCommandSent("I0Z"))).toBe(true); // Comando 'I0Z' enviado
    });

    test("Impresión de factura con impuestos y métodos de pago", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();
        driver.retryDelay = 0;

        await driver.connection.requestPort();
        driver.isConnected = true;

        const mockOrder = {
            partner: {
                vat: "J123456789",
                name: "EMPRESA TEST",
            },
            lines: [
                {
                    product_name: "Producto Exento",
                    fiscal_code: "0",
                    quantity: 1,
                    price_unit: 10.0,
                },
                {
                    product_name: "Producto Reducido",
                    fiscal_code: "2",
                    quantity: 1,
                    price_unit: 20.0,
                }
            ],
            payment_lines: [
                { payment_method_code: "01", amount: 10.0 },
                { payment_method_code: "02", amount: 20.0 },
            ],
            additional_lines: [],
            flag_21: "00",
            has_cashbox: false,
        };

        driver.connection.setNextResponse("STATUS");
        driver.connection.setResponseSequence(["ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK"]);
        driver.connection.setS1Payload(buildS1Payload({
            lastInvoiceNumber: 863,
            dailyClosureCounter: 18,
            serialMachine: "Z1F0022949",
        }));

        const result = await driver.printInvoice(mockOrder);

        expect(Boolean(result.success)).toBe(true); // Factura impresa exitosamente
        expect(result.invoiceNumber).toBe("863"); // Número de factura retornado desde S1
        expect(result.serial).toBe("Z1F0022949"); // Serial retornado desde S1
        expect(result.reportZ).toBe(19); // Z afectado calculado desde contador diario

        const asciiHistory = driver.connection.getSentCommands().map((cmd) => cmd.ascii);
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>iR*J123456789<ETX>")))).toBe(true); // RIF enviado
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>iS*EMPRESA TEST<ETX>")))).toBe(true); // Razón social enviada
        expect(Boolean(asciiHistory.some((cmd) => cmd.startsWith("<STX> 0000001000")))).toBe(true); // Línea exenta enviada (tax code 0)
        expect(Boolean(asciiHistory.some((cmd) => cmd.startsWith("<STX>\"0000002000")))).toBe(true); // Línea reducida enviada (tax code 2)
        // El método de mayor monto (02, 20.00) es el que cierra con 1XX; el otro (01) va como 2XX.
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>201000000001000<ETX>")))).toBe(true); // Pago parcial método 01 (no-cierre) enviado como 2XX
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>202000000002000<ETX>")))).toBe(false); // El método de cierre (02) NO se envía como 2XX
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>102<ETX>")))).toBe(true); // Cierre fiscal con 1XX (102, mayor monto)
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>101<ETX>")))).toBe(false); // No cierra con 101 (el método de mayor monto es 02, no 01)
    });

    // ============ TESTS DE IGTF (manual TFHKA v1.1.0) ============

    test("_isDivisaPaymentMethod clasifica códigos 01-19 como nacional y 20-24 como divisa", () => {
        const driver = new TfhkaDriver();

        expect(Boolean(driver._isDivisaPaymentMethod("01"))).toBe(false); // 01 es nacional
        expect(Boolean(driver._isDivisaPaymentMethod("19"))).toBe(false); // 19 es nacional (límite superior)
        expect(Boolean(driver._isDivisaPaymentMethod("00"))).toBe(false); // 00 es nacional
        expect(Boolean(driver._isDivisaPaymentMethod("20"))).toBe(true); // 20 es divisa (límite inferior)
        expect(Boolean(driver._isDivisaPaymentMethod("24"))).toBe(true); // 24 es divisa (límite superior)
        expect(Boolean(driver._isDivisaPaymentMethod("25"))).toBe(false); // 25 fuera de rango IGTF, no es divisa
        expect(Boolean(driver._isDivisaPaymentMethod(20))).toBe(true); // Acepta número además de string
    });

    test("_hasDivisaPayment detecta si algún pago de la orden es en divisa", () => {
        const driver = new TfhkaDriver();

        // Sin divisa si todos los métodos son 01-19
        expect(Boolean(
            driver._hasDivisaPayment([{ payment_method_code: "01" }, { payment_method_code: "02" }])
        )).toBe(false);
        // Detecta divisa si al menos un método está en 20-24
        expect(Boolean(
            driver._hasDivisaPayment([{ payment_method_code: "01" }, { payment_method_code: "20" }])
        )).toBe(true);
        expect(Boolean(driver._hasDivisaPayment([]))).toBe(false); // Sin pagos, no hay divisa
        expect(Boolean(driver._hasDivisaPayment(undefined))).toBe(false); // payment_lines undefined no rompe, retorna false
    });

    test("IGTF: pago con divisa cierra con 199 (no con 1XX) y envía TODOS los métodos como 2XX", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();
        driver.retryDelay = 0;

        await driver.connection.requestPort();
        driver.isConnected = true;

        const mockOrder = {
            partner: { vat: "J123456789", name: "EMPRESA DIVISA TEST" },
            lines: [
                { product_name: "Producto Gravado", fiscal_code: "1", quantity: 1, price_unit: 100.0 },
            ],
            payment_lines: [
                { payment_method_code: "01", amount: 40.0 },  // nacional (mayor monto, normalmente cerraría con 1XX)
                { payment_method_code: "20", amount: 60.0 },  // DIVISA -> dispara IGTF
            ],
            additional_lines: [],
            flag_21: "00",
            has_cashbox: false,
        };

        driver.connection.setNextResponse("STATUS");
        driver.connection.setResponseSequence(new Array(20).fill("ACK"));
        driver.connection.setS1Payload(buildS1Payload({
            lastInvoiceNumber: 900,
            dailyClosureCounter: 20,
            serialMachine: "Z1F0022949",
        }));

        const result = await driver.printInvoice(mockOrder);
        expect(Boolean(result.success)).toBe(true); // Factura con pago en divisa impresa exitosamente

        const asciiHistory = driver.connection.getSentCommands().map((cmd) => cmd.ascii);

        // Ambos métodos deben ir como 2XX (incluyendo el de mayor monto, que normalmente
        // cerraría con 1XX si no hubiera divisa involucrada)
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>201000000004000<ETX>")))).toBe(true); // Pago nacional 01 enviado como 2XX
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>220000000006000<ETX>")))).toBe(true); // Pago en divisa 20 enviado como 2XX

        // NO debe enviarse ningún cierre directo 1XX (ni 101 ni 120)
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>101<ETX>")))).toBe(false); // No se envía 1XX (101) con divisa presente
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>120<ETX>")))).toBe(false); // No se envía 1XX (120) con divisa presente

        // El cierre debe ser el 199 final (siempre presente al cerrar el documento)
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>199<ETX>")))).toBe(true); // Cierre con 199 (obligatorio con IGTF)
    });

    test("Sin divisa: comportamiento normal se mantiene (cierre con 1XX, no 199 de pago)", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();
        driver.retryDelay = 0;

        await driver.connection.requestPort();
        driver.isConnected = true;

        const mockOrder = {
            partner: { vat: "J123456789", name: "EMPRESA NACIONAL TEST" },
            lines: [
                { product_name: "Producto Gravado", fiscal_code: "1", quantity: 1, price_unit: 100.0 },
            ],
            payment_lines: [
                { payment_method_code: "01", amount: 40.0 },
                { payment_method_code: "02", amount: 60.0 },
            ],
            additional_lines: [],
            flag_21: "00",
            has_cashbox: false,
        };

        driver.connection.setNextResponse("STATUS");
        driver.connection.setResponseSequence(new Array(20).fill("ACK"));
        driver.connection.setS1Payload(buildS1Payload({
            lastInvoiceNumber: 901,
            dailyClosureCounter: 20,
            serialMachine: "Z1F0022949",
        }));

        const result = await driver.printInvoice(mockOrder);
        expect(Boolean(result.success)).toBe(true); // Factura sin divisa impresa exitosamente

        const asciiHistory = driver.connection.getSentCommands().map((cmd) => cmd.ascii);

        // El de mayor monto (02, 60.00) debe cerrar con 1XX; el otro (01) va como 2XX
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>201000000004000<ETX>")))).toBe(true); // Pago no-cierre 01 enviado como 2XX
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>202000000006000<ETX>")))).toBe(false); // El método de cierre NO se envía como 2XX
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>102<ETX>")))).toBe(true); // Cierre directo con 1XX (102, mayor monto)
    });

    test("_parseS25Data calcula el monto de IGTF como diferencia entre total con y sin IGTF", () => {
        const driver = new TfhkaDriver();

        // Campos: bases, impuesto, totalConIgtf, cantArticulos, totalSinIgtf, cantPagos, tipoDocumento
        const payload = "S2\n0000000010000\n0000000001600\n0000000014980\n000001\n0000000011600\n0001\n1";
        const data = driver._parseS25Data(payload);

        expect(Boolean(data)).toBe(true); // Parseo exitoso
        expect(data.subtotalBases).toBe(100.0); // Subtotal de bases imponibles correcto
        expect(data.subtotalTax).toBe(16.0); // Subtotal de impuesto correcto
        expect(data.totalWithoutIgtf).toBe(116.0); // Monto a pagar sin IGTF correcto
        expect(data.totalWithIgtf).toBe(149.8); // Monto a pagar incluyendo IGTF correcto
        expect(data.igtfAmount).toBe(33.8); // IGTF calculado como diferencia (149.80 - 116.00)
        expect(data.documentType).toBe("1"); // Tipo de documento: Factura
        expect(data.documentTypeLabel).toBe("Factura"); // Label de tipo de documento correcto
    });

    test("_parseS25Data retorna null con payload vacío o insuficiente", () => {
        const driver = new TfhkaDriver();
        expect(driver._parseS25Data("")).toBe(null); // Payload vacío retorna null
        expect(driver._parseS25Data("S2\n123")).toBe(null); // Payload con muy pocos campos retorna null
    });

    test("_formatDisplayAmount formatea con punto de miles y coma decimal (formato venezolano)", () => {
        const driver = new TfhkaDriver();

        expect(driver._formatDisplayAmount(15)).toBe("15,00"); // Monto simple sin miles
        expect(driver._formatDisplayAmount(50)).toBe("50,00"); // Monto simple sin miles (2)
        expect(driver._formatDisplayAmount(39290.94)).toBe("39.290,94"); // Monto con miles y decimales
        expect(driver._formatDisplayAmount(1234567.89)).toBe("1.234.567,89"); // Monto con múltiples separadores de miles
        expect(driver._formatDisplayAmount(0)).toBe("0,00"); // Monto cero
        expect(driver._formatDisplayAmount(999.5)).toBe("999,50"); // Redondeo a 2 decimales
        expect(driver._formatDisplayAmount(1000)).toBe("1.000,00"); // Límite exacto de mil
    });

    test("Nota de crédito con pago en divisa también cierra con 199 (no 1XX)", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();
        driver.retryDelay = 0;

        await driver.connection.requestPort();
        driver.isConnected = true;

        const creditNoteOrder = {
            partner: { vat: "V17527041", name: "Cliente NC Divisa" },
            invoice_affected: {
                number: "900",
                serial_machine: "Z1F0022949",
                date: "20/06/2026",
            },
            lines: [
                { product_name: "Producto Devuelto", product_code: "P001", fiscal_code: "1", quantity: 1, price_unit: 60 },
            ],
            payment_lines: [{ payment_method_code: "20", amount: 60 }],
            additional_lines: [],
            flag_21: "00",
            has_cashbox: false,
        };

        driver.connection.setNextResponse("STATUS");
        driver.connection.setResponseSequence(new Array(20).fill("ACK"));
        driver.connection.setS1Payload(buildS1Payload({
            lastInvoiceNumber: 900,
            lastNCNumber: 1235,
            dailyClosureCounter: 20,
            serialMachine: "Z1F0022949",
        }));

        const result = await driver.printCreditNote(creditNoteOrder);
        expect(Boolean(result.success)).toBe(true); // NC con pago en divisa impresa exitosamente

        const asciiHistory = driver.connection.getSentCommands().map((cmd) => cmd.ascii);
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>220000000006000<ETX>")))).toBe(true); // Pago en divisa enviado como 2XX
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>120<ETX>")))).toBe(false); // No se envía cierre directo 1XX con divisa
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>199<ETX>")))).toBe(true); // Cierre con 199
    });

    test("Impresión de nota de crédito con secuencia fiscal correcta", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();
        driver.retryDelay = 0;

        await driver.connection.requestPort();
        driver.isConnected = true;

        const creditNoteOrder = {
            partner: {
                vat: "V17527041",
                name: "Cliente NC",
            },
            invoice_affected: {
                number: "863",
                serial_machine: "Z1F0022949",
                date: "20/06/2026",
            },
            lines: [
                {
                    product_name: "Producto Devuelto",
                    product_code: "P001",
                    fiscal_code: "1",
                    quantity: 2,
                    price_unit: 50,
                },
            ],
            payment_lines: [{ payment_method_code: "01", amount: 100 }],
            additional_lines: ["OPERADOR: TEST"],
            flag_21: "00",
            has_cashbox: false,
        };

        driver.connection.setNextResponse("STATUS");
        driver.connection.setResponseSequence(["ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK", "ACK"]);
        driver.connection.setS1Payload(buildS1Payload({
            lastInvoiceNumber: 863,
            lastNCNumber: 1234,
            dailyClosureCounter: 18,
            serialMachine: "Z1F0022949",
        }));

        const result = await driver.printCreditNote(creditNoteOrder);

        expect(Boolean(result.success)).toBe(true); // Nota de crédito impresa exitosamente
        expect(result.invoiceNumber).toBe("1234"); // Número de nota de crédito leído desde S1

        const fiscalCommands = driver.connection
            .getSentCommands()
            .map((cmd) => cmd.ascii)
            .filter((cmd) => cmd.includes("<STX>"));

        expect(Boolean(fiscalCommands.some((cmd) => cmd.includes("PH01")))).toBe(false); // No se envía PH01 en NC
        expect(Boolean(fiscalCommands[0].includes("<STX>iR*V17527041<ETX>"))).toBe(true); // NC inicia con iR*
        expect(Boolean(fiscalCommands[1].includes("<STX>iS*Cliente NC<ETX>"))).toBe(true); // NC continúa con iS*
        expect(Boolean(fiscalCommands.some((cmd) => cmd.includes("<STX>iF*00000863<ETX>")))).toBe(true); // Factura afectada enviada en iF*
        expect(Boolean(fiscalCommands.some((cmd) => cmd.includes("<STX>iI*Z1F0022949<ETX>")))).toBe(true); // Serial afectado enviado en iI*
        expect(Boolean(fiscalCommands.some((cmd) => cmd.includes("<STX>iD*20/06/2026<ETX>")))).toBe(true); // Fecha afectada enviada en iD*
        expect(Boolean(fiscalCommands.some((cmd) => cmd.includes("<STX>d1000000500000002000|P001|Producto Devuelto<ETX>")))).toBe(true); // Línea NC enviada con prefijo d
        expect(Boolean(fiscalCommands.some((cmd) => cmd.includes("<STX>101<ETX>")))).toBe(true); // Cierre NC con método de pago correcto
    });

    test("Código fiscal t0 se mapea como exento", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();
        driver.retryDelay = 0;

        await driver.connection.requestPort();
        driver.isConnected = true;

        const orderWithTaxPrefix = {
            partner: {
                vat: "V12345678",
                name: "CLIENTE EXENTO",
            },
            lines: [
                {
                    product_name: "Producto Exento Prefijo",
                    fiscal_code: "t0",
                    quantity: 1,
                    price_unit: 10.0,
                },
            ],
            payment_lines: [{ payment_method_code: "01", amount: 10.0 }],
            additional_lines: [],
            flag_21: "00",
            has_cashbox: false,
        };

        driver.connection.setNextResponse("STATUS");
        driver.connection.setResponseSequence(new Array(20).fill("ACK"));
        driver.connection.setS1Payload(buildS1Payload({
            lastInvoiceNumber: 1001,
            dailyClosureCounter: 20,
            serialMachine: "Z1F0022949",
        }));

        const result = await driver.printInvoice(orderWithTaxPrefix);
        expect(Boolean(result.success)).toBe(true); // Factura con fiscal_code t0 impresa exitosamente

        const asciiHistory = driver.connection.getSentCommands().map((cmd) => cmd.ascii);
        const exemptLine = asciiHistory.find((cmd) => cmd.includes("Producto Exento Prefijo"));
        expect(Boolean(exemptLine && exemptLine.startsWith("<STX> 0000001000"))).toBe(true); // La línea se envía como exenta (prefijo espacio)
        expect(Boolean(exemptLine && exemptLine.startsWith("<STX>!0000001000"))).toBe(false); // La línea no se envía como gravada (G)
    });

    test("_applyDiscount aplica porcentaje sobre la base y redondea", () => {
        // Espejo del helper en PosStore._applyDiscount sin requerir PosStore.
        const round = (value, decimals = 2) => Number(Number(value).toFixed(decimals));
        const applyDiscount = (unitPrice, percent) =>
            round(Number(unitPrice || 0) * (1 - Number(percent || 0) / 100));

        expect(applyDiscount(100, 10)).toBe(90); // 10% sobre 100 → 90.00
        expect(applyDiscount(100, 0)).toBe(100); // 0% sobre 100 → 100.00
        expect(applyDiscount(0, 10)).toBe(0); // Cualquier % sobre 0 → 0.00
        expect(applyDiscount(90, 10)).toBe(81); // Cascada: 100 → 90 → 81
        expect(applyDiscount(99.99, 10)).toBe(89.99); // Redondeo a 2 decimales
        expect(applyDiscount(50, 50)).toBe(25); // 50% sobre 50 → 25.00
        expect(applyDiscount(1, 100)).toBe(0); // 100% sobre 1 → 0.00
    });

    test("Descuento global (Strategy A) no envía q- y refleja monto en líneas", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();
        driver.retryDelay = 0;

        await driver.connection.requestPort();
        driver.isConnected = true;

        // Strategy A: el PosStore ya aplicó la cascada y la tasa global al price_unit.
        // Cada línea positiva llega con su precio base ya neto de descuento.
        const orderWithGlobalDiscount = {
            partner: {
                vat: "J123456789",
                name: "CLIENTE DESCUENTO",
            },
            lines: [
                {
                    product_name: "Producto A",
                    product_code: "A001",
                    fiscal_code: "1",
                    quantity: 1,
                    price_unit: 85,   // 100 base - 15% (10% global sobre base 100)
                },
            ],
            payment_lines: [{ payment_method_code: "01", amount: 85 }],
            global_discount_amount: 15,
            global_discount_rate: 15,
            global_clamped: false,
            additional_lines: [],
            flag_21: "00",
            has_cashbox: false,
        };

        driver.connection.setNextResponse("STATUS");
        driver.connection.setResponseSequence(new Array(30).fill("ACK"));
        driver.connection.setS1Payload(buildS1Payload({
            lastInvoiceNumber: 999,
            dailyClosureCounter: 20,
            serialMachine: "Z1F0022949",
        }));

        const result = await driver.printInvoice(orderWithGlobalDiscount);
        expect(Boolean(result.success)).toBe(true); // Factura con descuento global impresa exitosamente

        const asciiHistory = driver.connection.getSentCommands().map((cmd) => cmd.ascii);
        const close101Count = asciiHistory.filter((cmd) => cmd.includes("<STX>101<ETX>")).length;
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>q-")))).toBe(false); // No se envía q- con Strategy A
        // Línea informativa de descuento global con porcentaje y monto presentes (formato venezolano: coma decimal)
        expect(Boolean(
            asciiHistory.some((cmd) => cmd.includes("i00DESC. GLOBAL = 15,00<ETX>"))
        )).toBe(true);
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("Descuento Global<ETX>")))).toBe(false); // No hay línea negativa enviada como item
        expect(Boolean(asciiHistory.some((cmd) => cmd.includes("<STX>201000000008500<ETX>")))).toBe(false); // Pago único no se envía como parcial 2XX
        expect(close101Count).toBe(1); // Pago único con método 01 envía 101 una sola vez
        expect(result.global_discount_amount).toBe(15); // Monto del descuento global retornado al caller
        expect(result.global_discount_rate).toBe(15); // Tasa del descuento global retornada al caller
        expect(Boolean(result.global_clamped)).toBe(false); // Sin clamp en este caso
    });

    test("Descuento global (Strategy A) emite aviso adicional cuando es clampado", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();
        driver.retryDelay = 0;

        await driver.connection.requestPort();
        driver.isConnected = true;

        const orderWithClampedDiscount = {
            partner: {
                vat: "J123456789",
                name: "CLIENTE DESCUENTO",
            },
            lines: [
                {
                    product_name: "Producto A",
                    product_code: "A001",
                    fiscal_code: "1",
                    quantity: 1,
                    price_unit: 0,    // Base reducida al 100% por el clamp del PosStore
                },
            ],
            payment_lines: [{ payment_method_code: "01", amount: 0 }],
            global_discount_amount: 50,
            global_discount_rate: 100,
            global_clamped: true,
            additional_lines: [],
            flag_21: "00",
            has_cashbox: false,
        };

        driver.connection.setNextResponse("STATUS");
        driver.connection.setResponseSequence(new Array(30).fill("ACK"));
        driver.connection.setS1Payload(buildS1Payload({
            lastInvoiceNumber: 1000,
            dailyClosureCounter: 21,
            serialMachine: "Z1F0022949",
        }));

        const result = await driver.printInvoice(orderWithClampedDiscount);
        expect(Boolean(result.success)).toBe(true); // Factura con descuento clampado impresa

        const asciiHistory = driver.connection.getSentCommands().map((cmd) => cmd.ascii);
        // Línea informativa del descuento clampado presente (formato venezolano: coma decimal)
        expect(Boolean(
            asciiHistory.some((cmd) => cmd.includes("i00DESC. GLOBAL = 50,00<ETX>"))
        )).toBe(true);
        // Línea de aviso por clamp emitida
        expect(Boolean(
            asciiHistory.some((cmd) => cmd.includes("i01DESC. GLOBAL EXCEDIO SUBTOTAL<ETX>"))
        )).toBe(true);
        expect(Boolean(result.global_clamped)).toBe(true); // Bandera global_clamped=true hacia el caller
    });

    test("Header y footer del POS se envían como iXX", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();
        driver.retryDelay = 0;

        await driver.connection.requestPort();
        driver.isConnected = true;

        const orderWithHeaderFooter = {
            partner: {
                vat: "V12345678",
                name: "CLIENTE HEADER",
                address: "Av Principal Torre A Piso 2",
                phone: "0212-0000000",
            },
            lines: [
                {
                    product_name: "Producto Header Footer",
                    product_code: "HF01",
                    fiscal_code: "1",
                    quantity: 1,
                    price_unit: 10,
                },
            ],
            payment_lines: [{ payment_method_code: "01", amount: 10 }],
            header_lines: ["ENCABEZADO 1", "ENCABEZADO 2"],
            footer_lines: ["PIE 1"],
            additional_lines: ["OPERADOR: QA"],
            flag_21: "00",
            has_cashbox: false,
        };

        driver.connection.setNextResponse("STATUS");
        driver.connection.setResponseSequence(new Array(30).fill("ACK"));
        driver.connection.setS1Payload(buildS1Payload({
            lastInvoiceNumber: 1000,
            dailyClosureCounter: 20,
            serialMachine: "Z1F0022949",
        }));

        const result = await driver.printInvoice(orderWithHeaderFooter);
        expect(Boolean(result.success)).toBe(true); // Factura con header/footer impresa exitosamente

        const fiscalCommands = driver.connection.getSentCommands().map((cmd) => cmd.ascii);

        expect(Boolean(fiscalCommands.some((cmd) => cmd.includes("<STX>i02ENCABEZADO 1<ETX>")))).toBe(true); // Header línea 1 enviada
        expect(Boolean(fiscalCommands.some((cmd) => cmd.includes("<STX>i03ENCABEZADO 2<ETX>")))).toBe(true); // Header línea 2 enviada
        expect(Boolean(fiscalCommands.some((cmd) => cmd.includes("<STX>i00PIE 1<ETX>")))).toBe(true); // Footer línea 1 enviada
        expect(Boolean(fiscalCommands.some((cmd) => cmd.includes("<STX>i01OPERADOR: QA<ETX>")))).toBe(true); // Línea adicional se envía después del footer
    });

    test("Lectura y parsing de S3", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();

        await driver.connection.requestPort();
        driver.isConnected = true;

        const s3Payload = "S311600\n20800\n10000\n101230405";
        driver.connection.setNextResponse(s3Payload);

        const result = await driver.readS3Data();

        expect(Boolean(result.success)).toBe(true); // S3 leído correctamente
        expect(result.data.tax1.type).toBe("1"); // Tipo tasa 1 parseado
        expect(result.data.tax1.value).toBe(16); // Valor tasa 1 parseado
        expect(result.data.tax2.typeLabel).toBe("Incluido"); // Tipo de tasa 2 interpretado
        expect(result.data.igtf.value).toBe(1.23); // IGTF parseado con 2 decimales implícitos
        expect(result.data.systemFlags).toEqual([4, 5]); // Flags de sistema parseados
    });

    test("Error de conexión a la máquina fiscal", async () => {
        const driver = new TfhkaDriver();
        driver.connection = new MockSerialConnection();
        driver.isConnected = false;

        const result = await driver.printInvoice({
            partner: { vat: "J000000001", name: "SIN CONEXION" },
            lines: [{ product_name: "Producto", fiscal_code: "1", quantity: 1, price_unit: 10 }],
            payment_lines: [{ payment_method_code: "01", amount: 10 }],
            additional_lines: [],
            flag_21: "00",
            has_cashbox: false,
        });

        expect(Boolean(result.success)).toBe(false); // No imprime si la impresora está desconectada
        expect(Boolean(result.error.includes("Impresora no conectada"))).toBe(true); // Retorna mensaje de conexión
    });
});
