import { Component, useEffect, useRef, useState } from "@odoo/owl";

// Spanish (LatAm) QWERTY letter rows, lowercase — Ñ included between L and
// the row's end, same spot as a physical Spanish keyboard. Uppercase is a
// display-only transform (see displayLetter/onLetterClick): the component
// never manages two full layouts, just a "shift" flag.
const NUMBER_ROW = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"];
const LETTER_ROW_1 = ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"];
const LETTER_ROW_2 = ["a", "s", "d", "f", "g", "h", "j", "k", "l", "ñ"];
const LETTER_ROW_3 = ["z", "x", "c", "v", "b", "n", "m"];

// Pure helper (exported for unit testing, see
// static/tests/unit/kiosk_keyboard.test.js): the whole point of "shift" is
// this one transform, kept outside the component so it is testable without
// mounting an Owl component.
export function applyShift(letter, shift) {
    return shift ? letter.toUpperCase() : letter;
}

export { NUMBER_ROW, LETTER_ROW_1, LETTER_ROW_2, LETTER_ROW_3 };

/**
 * On-screen keyboard for the Kiosk, no external libraries (ticket 80343,
 * point 6). Purely presentational: it does not know which input is
 * "active" — the parent tracks that and passes an `onKey` callback that
 * receives either a literal character (already upper/lowercased) or one of
 * the action strings "backspace" / "space".
 *
 * Two modes:
 *   - "text" (default): full QWERTY + Ñ + numbers + space/backspace/shift.
 *   - "numeric": digits-only grid, for phone/cédula fields. Reuses the same
 *     3x4 layout and classes as identification_page's own o_ve_numpad
 *     (1-9, then backspace/0/clear) so the two on-screen keypads look and
 *     behave identically.
 */
export class KioskKeyboard extends Component {
    static template = "l10n_ve_pos_self_order.KioskKeyboard";
    static props = {
        mode: { type: String, optional: true },
        onKey: Function,
    };
    static defaultProps = {
        mode: "text",
    };

    setup() {
        this.state = useState({ shift: false });
        // The keyboard renders at the bottom of long forms (new customer:
        // name, phone, address), so its last row (⌫ / 0 / C in numeric mode)
        // can end up below the fold of the page's scroll container. Bring it
        // fully into view whenever it appears or switches layout.
        this.rootRef = useRef("root");
        useEffect(
            () => this.rootRef.el?.scrollIntoView({ block: "nearest", behavior: "smooth" }),
            () => [this.props.mode]
        );
    }

    get isNumeric() {
        return this.props.mode === "numeric";
    }

    get numberKeys() {
        return NUMBER_ROW;
    }

    get letterRow1() {
        return LETTER_ROW_1;
    }

    get letterRow2() {
        return LETTER_ROW_2;
    }

    get letterRow3() {
        return LETTER_ROW_3;
    }

    // Same numpad layout as identification_page.js's numpadKeys (3×4:
    // 1-9, then backspace / 0 / clear).
    get numpadKeys() {
        return [
            { label: "1", value: "1" },
            { label: "2", value: "2" },
            { label: "3", value: "3" },
            { label: "4", value: "4" },
            { label: "5", value: "5" },
            { label: "6", value: "6" },
            { label: "7", value: "7" },
            { label: "8", value: "8" },
            { label: "9", value: "9" },
            { label: "⌫", value: "backspace", action: true },
            { label: "0", value: "0" },
            { label: "C", value: "clear", action: true },
        ];
    }

    displayLetter(letter) {
        return applyShift(letter, this.state.shift);
    }

    toggleShift() {
        this.state.shift = !this.state.shift;
    }

    onLetterClick(letter) {
        this.props.onKey(applyShift(letter, this.state.shift));
    }

    onNumpadClick(value) {
        this.props.onKey(value);
    }

    onBackspace() {
        this.props.onKey("backspace");
    }

    onSpace() {
        this.props.onKey("space");
    }
}
