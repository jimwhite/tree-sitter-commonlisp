"""
Test that the commonlisp_noformat grammar correctly parses ACL2 source files.

Reproduces a bug where tree-sitter splits certain (defun ...) forms into a
standalone '(' token plus a 'defun_header' node (and subsequent comment/body
fragments), instead of parsing the whole form as a single 'list_lit'.

The bug manifests in history-management.lisp (and other files) causing the
.lisp → .ipynb converter to put '(' in one notebook cell and the rest of the
form in later cells — producing "split-cell reader errors" at build time.

Run:  python -m pytest test_noformat_parse.py -v
"""

import os
import tree_sitter
import tree_sitter_commonlisp_noformat as tscl

import pytest

LANG = tree_sitter.Language(tscl.language())

ACL2_DIR = os.environ.get("ACL2_DIR", "/home/acl2")
HISTORY_MGMT = os.path.join(ACL2_DIR, "history-management.lisp")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def parse(src: bytes):
    parser = tree_sitter.Parser(LANG)
    return parser.parse(src)


def broken_root_nodes(src: bytes):
    """Return root-level nodes that indicate a parse break.

    A well-formed Common Lisp source should have only these node types at the
    root level:
        list_lit   – top-level forms  (defun …), (defmacro …), etc.
        comment    – ; … or #| … |#
        sym_lit    – bare symbols (rare but legal)
        quoting_lit, unquoting_lit, etc.

    A standalone '(' or 'ERROR' node at root level means tree-sitter failed to
    group the tokens into a proper form — causing the converter to split the
    form across multiple notebook cells.

    We do NOT flag list_lit nodes that have has_error=True internally, because
    tree-sitter still found matching parens and the converter produces a
    correct cell.
    """
    tree = parse(src)
    bad = []
    for child in tree.root_node.children:
        if child.type in ("(", "ERROR"):
            bad.append(child)
    return bad


# ---------------------------------------------------------------------------
# Minimal reproducer
# ---------------------------------------------------------------------------

MINIMAL_GOOD = b"""\
(defun big-d-little-d-clique (names ens wrld)
  (let ((ans (big-d-little-d-name (car names) ens wrld)))
    (cond ((eql ans #\\d) #\\d)
          (t (big-d-little-d-clique1 (cdr names) ens wrld ans)))))

(defun big-d-little-d-event (ev-tuple ens wrld)
  (let ((namex (access-event-tuple-namex ev-tuple)))
    (case namex
          (0 #\\Space)
          (t (big-d-little-d-name namex ens wrld)))))
"""


def test_minimal_two_forms():
    """Two consecutive defuns using #\\d and #\\Space must each parse as list_lit."""
    bad = broken_root_nodes(MINIMAL_GOOD)
    assert bad == [], (
        f"Expected no broken nodes, got {len(bad)}: "
        + ", ".join(
            f"type={n.type} line={n.start_point[0]+1}"
            for n in bad
        )
    )


# ---------------------------------------------------------------------------
# Full-file test (history-management.lisp)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.path.exists(HISTORY_MGMT),
    reason=f"{HISTORY_MGMT} not found",
)
def test_history_management_no_broken_nodes():
    """history-management.lisp must parse without any broken root nodes."""
    with open(HISTORY_MGMT, "rb") as f:
        src = f.read()

    bad = broken_root_nodes(src)

    # Provide actionable diagnostics
    if bad:
        lines = src.split(b"\n")
        details = []
        for node in bad:
            line_no = node.start_point[0] + 1
            context = lines[node.start_point[0]][: 80].decode("utf-8", errors="replace")
            details.append(f"  line {line_no}: type={node.type!r}  {context!r}")
        msg = (
            f"{len(bad)} broken root node(s) in {HISTORY_MGMT}:\n"
            + "\n".join(details)
        )
        pytest.fail(msg)


# ---------------------------------------------------------------------------
# Scan every .lisp file in ACL2_DIR
# ---------------------------------------------------------------------------

def _acl2_lisp_files():
    """Yield (stem, path) for every .lisp in ACL2_DIR."""
    if not os.path.isdir(ACL2_DIR):
        return
    for name in sorted(os.listdir(ACL2_DIR)):
        if name.endswith(".lisp"):
            yield name[:-5], os.path.join(ACL2_DIR, name)


@pytest.mark.skipif(
    not os.path.isdir(ACL2_DIR),
    reason=f"{ACL2_DIR} not found",
)
@pytest.mark.parametrize("stem,path", list(_acl2_lisp_files()), ids=[s for s, _ in _acl2_lisp_files()])
def test_acl2_file_no_broken_nodes(stem, path):
    """Every ACL2 .lisp file must parse without broken root nodes."""
    with open(path, "rb") as f:
        src = f.read()

    bad = broken_root_nodes(src)

    if bad:
        lines = src.split(b"\n")
        details = []
        for node in bad[:10]:  # cap output
            line_no = node.start_point[0] + 1
            context = lines[node.start_point[0]][:80].decode("utf-8", errors="replace")
            details.append(f"  line {line_no}: type={node.type!r}  {context!r}")
        if len(bad) > 10:
            details.append(f"  ... and {len(bad) - 10} more")
        msg = (
            f"{len(bad)} broken root node(s) in {path}:\n"
            + "\n".join(details)
        )
        pytest.fail(msg)
