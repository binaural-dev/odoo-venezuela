import { test, expect, describe } from "@odoo/hoot";
import {
    applyShift,
    NUMBER_ROW,
    LETTER_ROW_1,
    LETTER_ROW_2,
    LETTER_ROW_3,
} from "@l10n_ve_pos_self_order/app/components/kiosk_keyboard/kiosk_keyboard";

// Unit tests de las partes PURAS de KioskKeyboard (ticket 80343, punto 6):
// el transform de "shift" y la composición de las filas del layout. La
// interacción con el DOM/onKey se deja a la verificación manual (el
// componente no expone más lógica pura fuera de esto).

describe("applyShift", () => {
    test("shift activo pasa a mayúscula", () => {
        expect(applyShift("a", true)).toBe("A");
        expect(applyShift("ñ", true)).toBe("Ñ");
    });

    test("shift inactivo deja la letra tal cual (minúscula)", () => {
        expect(applyShift("a", false)).toBe("a");
        expect(applyShift("ñ", false)).toBe("ñ");
    });
});

describe("layout QWERTY + Ñ + números", () => {
    test("fila de números: 1-9 y 0", () => {
        expect(NUMBER_ROW).toEqual(["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]);
    });

    test("la Ñ está en la segunda fila de letras", () => {
        expect(LETTER_ROW_2.includes("ñ")).toBe(true);
    });

    test("26 letras del abecedario español + ñ, sin duplicados, entre las 3 filas", () => {
        const allKeys = [...LETTER_ROW_1, ...LETTER_ROW_2, ...LETTER_ROW_3];
        expect(allKeys.length).toBe(27);
        expect(new Set(allKeys).size).toBe(27);
        expect(allKeys.every((letter) => letter === letter.toLowerCase())).toBe(true);
    });
});
