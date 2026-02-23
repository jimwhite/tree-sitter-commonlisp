"""Bisect history-management.lisp to find the minimal prefix that triggers
the tree-sitter parse break at the (defun big-d-little-d-event ...) form."""

import tree_sitter
import tree_sitter_commonlisp_noformat as tscl

LANG = tree_sitter.Language(tscl.language())
TARGET = b"(defun big-d-little-d-event"
FILE = "/home/acl2/history-management.lisp"


def has_paren_break(src: bytes) -> bool:
    parser = tree_sitter.Parser(LANG)
    tree = parser.parse(src)
    return any(c.type == "(" for c in tree.root_node.children)


with open(FILE, "rb") as f:
    full = f.read()

lines = full.split(b"\n")

# The target defun is at line 6088 (0-indexed 6087).
# Find the end — look for the next top-level ( after target.
target_idx = next(i for i, l in enumerate(lines) if TARGET in l)
suffix_end = target_idx + 1
for i in range(target_idx + 1, len(lines)):
    if lines[i].startswith(b"("):
        suffix_end = i
        break
suffix = b"\n".join(lines[target_idx:suffix_end])

print(f"Target form at line {target_idx + 1}")
print(f"Suffix: {len(suffix)} bytes, lines {target_idx+1}-{suffix_end}")
print()

# Sanity: suffix alone should NOT break
if has_paren_break(suffix):
    print("*** Suffix ALONE breaks! Investigating the form itself...")
    # Try without the comments containing #\
    no_hash_comments = []
    for line in lines[target_idx:suffix_end]:
        if line.lstrip().startswith(b";") and b"#\\" in line:
            no_hash_comments.append(b"; [comment with char lit removed]")
        else:
            no_hash_comments.append(line)
    cleaned = b"\n".join(no_hash_comments)
    print(f"  Without #\\ comments: breaks={has_paren_break(cleaned)}")

    # Try with just the code (no comments)
    code_only = [l for l in lines[target_idx:suffix_end]
                 if not l.lstrip().startswith(b";")]
    code_src = b"\n".join(code_only)
    print(f"  Code only (no comments): breaks={has_paren_break(code_src)}")
    # Try replacing (defun in case clause
    case_fix = code_src.replace(b"(defun defthm", b"(DEFUN-TEST defthm")
    print(f"  Replace (defun in case: breaks={has_paren_break(case_fix)}")

    # Minimal: just the case clause
    mini = b"""(defun big-d-little-d-event (ev-tuple ens wrld)
  (case (access-event-tuple-type ev-tuple)
        ((defun defthm defaxiom)
         (big-d-little-d-name namex ens wrld))))"""
    print(f"  Minimal with (defun in case: breaks={has_paren_break(mini)}")

    # The full code-only form has both (defun in case AND #\Space
    # Test: (defun in case + #\Space
    mini3 = b"""(defun big-d-little-d-event (ev-tuple ens wrld)
  (case (access-event-tuple-type ev-tuple)
        ((defun defthm defaxiom)
         (big-d-little-d-name namex ens wrld))
        (otherwise #\\Space)))"""
    print(f"  (defun in case + #\\Space: breaks={has_paren_break(mini3)}")

    # Without #\Space
    mini4 = b"""(defun big-d-little-d-event (ev-tuple ens wrld)
  (case (access-event-tuple-type ev-tuple)
        ((defun defthm defaxiom)
         (big-d-little-d-name namex ens wrld))
        (otherwise nil)))"""
    print(f"  (defun in case + nil: breaks={has_paren_break(mini4)}")

    # defuns too?
    mini5 = b"""(defun big-d-little-d-event (ev-tuple ens wrld)
  (case (access-event-tuple-type ev-tuple)
        ((defun defthm defaxiom)
         (big-d-little-d-name namex ens wrld))
        (defuns (big-d-little-d-clique namex ens wrld))
        (otherwise nil)))"""
    print(f"  with defuns clause: breaks={has_paren_break(mini5)}")

    # Exact reproduction of the actual code (no comments)
    exact = b"""(defun big-d-little-d-event (ev-tuple ens wrld)
  (let ((namex (access-event-tuple-namex ev-tuple)))
    (case (access-event-tuple-type ev-tuple)
          ((defun defthm defaxiom)
           (big-d-little-d-name namex ens wrld))
          (defuns (big-d-little-d-clique namex ens wrld))
          (defstobj (big-d-little-d-clique (cddr namex) ens wrld))
          (otherwise #\\Space))))"""
    print(f"  exact code reproduction: breaks={has_paren_break(exact)}")

    # Without (defun in case
    exact2 = exact.replace(b"(defun defthm", b"(xxfun defthm")
    print(f"  exact without defun in case: breaks={has_paren_break(exact2)}")

    # Without defstobj
    exact3 = exact.replace(b"(defstobj", b"(xxstobj")
    print(f"  exact without defstobj: breaks={has_paren_break(exact3)}")

    # With let but without (defun in case — to confirm it's the combo
    exact5 = b"""(defun big-d-little-d-event (ev-tuple ens wrld)
  (let ((namex (access-event-tuple-namex ev-tuple)))
    (case (access-event-tuple-type ev-tuple)
          ((xxfun defthm defaxiom)
           (big-d-little-d-name namex ens wrld))
          (defuns (big-d-little-d-clique namex ens wrld))
          (defstobj (big-d-little-d-clique (cddr namex) ens wrld))
          (otherwise #\\Space))))"""
    print(f"  let + no defun in case: breaks={has_paren_break(exact5)}")

    # Minimal: just let + (defun in case
    exact6 = b"""(defun foo (x)
  (let ((y x))
    (case y
          ((defun bar) (f y)))))"""
    print(f"  minimal let+defun: breaks={has_paren_break(exact6)}")

    # Build up from minimal to exact — what addition triggers it?
    tests = {
        "2 case clauses": b"""(defun foo (x)
  (let ((y x))
    (case y
          ((defun a) (f x))
          (otherwise (g x)))))""",

        "3 case clauses": b"""(defun foo (x)
  (let ((y x))
    (case y
          ((defun a b) (f x))
          (c (g x))
          (otherwise (h x)))))""",

        "4 case clauses": b"""(defun foo (x)
  (let ((y x))
    (case y
          ((defun a b) (f x))
          (c (g x))
          (d (h x))
          (otherwise (i x)))))""",

    # Start from the breaking exact and simplify to find the trigger
    # The breaking exact uses real function names, the working one uses short names
    tests2 = {
        "long fn name": b"""(defun big-d-little-d-event (ev-tuple ens wrld)
  (let ((namex (bar ev-tuple)))
    (case (baz ev-tuple)
          ((defun defthm defaxiom)
           (qux namex ens wrld))
          (defuns (quux namex ens wrld))
          (defstobj (quux (cddr namex) ens wrld))
          (otherwise #\\Space))))""",

        "long accessor": b"""(defun foo (ev-tuple ens wrld)
  (let ((namex (access-event-tuple-namex ev-tuple)))
    (case (baz ev-tuple)
          ((defun defthm defaxiom)
           (qux namex ens wrld))
          (defuns (quux namex ens wrld))
          (defstobj (quux (cddr namex) ens wrld))
          (otherwise #\\Space))))""",

        "long case expr": b"""(defun foo (ev-tuple ens wrld)
  (let ((namex (bar ev-tuple)))
    (case (access-event-tuple-type ev-tuple)
          ((defun defthm defaxiom)
           (qux namex ens wrld))
          (defuns (quux namex ens wrld))
          (defstobj (quux (cddr namex) ens wrld))
          (otherwise #\\Space))))""",

        "long called fns": b"""(defun foo (ev-tuple ens wrld)
  (let ((namex (bar ev-tuple)))
    (case (baz ev-tuple)
          ((defun defthm defaxiom)
           (big-d-little-d-name namex ens wrld))
          (defuns (big-d-little-d-clique namex ens wrld))
          (defstobj (big-d-little-d-clique (cddr namex) ens wrld))
          (otherwise #\\Space))))""",
    }
    for label, src in tests2.items():
        print(f"  {label}: breaks={has_paren_break(src)}")
else:
    print("Suffix alone OK")

# Full file SHOULD break
assert has_paren_break(full), "Full file doesn't break — nothing to bisect"

# Binary search: find the latest start line whose prefix + suffix breaks
lo, hi = 0, target_idx - 1
while lo < hi:
    mid = (lo + hi + 1) // 2
    chunk = b"\n".join(lines[mid:suffix_end])
    if has_paren_break(chunk):
        lo = mid  # still breaks, try starting later
    else:
        hi = mid - 1  # doesn't break, need earlier content

# lo is the latest start that still breaks
print(f"Latest start line that triggers break: {lo + 1}")
print(f"Line content: {lines[lo][:100]}")
print()

# Now find the EARLIEST start that still breaks (i.e., the single trigger line)
# Try removing individual lines from lo..target_idx to find which one is essential
# First, let's narrow: does just line lo + suffix break?
just_one = lines[lo] + b"\n\n" + suffix
if has_paren_break(just_one):
    print(f"Single trigger line {lo+1}: {lines[lo][:120]}")
else:
    # Need more context — show the critical window
    print(f"Need range {lo+1} to {target_idx} to trigger break")
    # Show the critical lines
    for i in range(lo, min(lo + 20, target_idx)):
        print(f"  {i+1}: {lines[i][:100].decode('utf-8', errors='replace')}")
