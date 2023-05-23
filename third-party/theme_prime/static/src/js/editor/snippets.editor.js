/** @odoo-module **/

import { SnippetsMenu } from 'website.snippet.editor';
import { _lt } from 'web.core';

SnippetsMenu.include({
    optionsTabStructure: [...SnippetsMenu.prototype.optionsTabStructure, ['theme-prime-options', _lt("Theme Prime Options")]],
});
