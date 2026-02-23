/*
 * grammar.js — commonlisp_noformat variant of tree-sitter-commonlisp
 *
 * Inherits the full Common Lisp grammar but replaces str_lit with a
 * simple opaque "..." token.  The CL reader doesn't parse format
 * directives inside strings — FORMAT interprets them at runtime — so
 * for structural parsing (top-level form extraction, notebook
 * generation) we only need correct string boundaries.
 *
 * The upstream grammar parses format specifiers inside strings for
 * syntax highlighting, but this causes tree-sitter error recovery
 * issues when structural characters like ()[]{}; appear in format
 * strings.  This variant avoids those problems entirely.
 *
 * Usage:
 *   cd commonlisp_noformat && tree-sitter generate
 *
 * Distributed under terms of the MIT license.
 */

const commonlisp = require("../grammar");

const STRING =
    token(seq('"',
        repeat(/[^"\\]/),
        repeat(seq("\\",
            /./,
            repeat(/[^"\\]/))),
        '"'));

module.exports = grammar(commonlisp, {
    name: 'commonlisp_noformat',

    rules: {
        // Override: treat strings as opaque tokens (no format specifier
        // sub-structure).  This eliminates all error-recovery issues
        // caused by structural characters appearing inside format strings.
        str_lit: _ => STRING,
    },
});
