# Hierarchical Petri Nets (HCPNs) in `cpnpy`

Hierarchical Petri Nets (HPNs) or Hierarchical Colored Petri Nets (HCPNs) extend traditional Petri nets (or Colored Petri Nets, CPNs) with **hierarchical abstraction**. In a Hierarchical Petri Net, a transition can be replaced (or “substituted”) by another entire (sub)Petri net. This allows modeling complex, multi-level systems more cleanly by breaking them into modules.

**Key Advantages of Hierarchical Modeling:**
- **Modularity:** Each sub-net encapsulates part of the system logic.  
- **Reusability:** Sub-net modules (e.g., “Payment Process”) can be reused in multiple parent contexts.  
- **Scalability:** Large systems become more manageable when broken into layers, each focusing on a coherent subset of functionality.

In `cpnpy`, hierarchical CPNs (HCPNs) are handled by two main components:

1. **`HCPN` Class** (`cpnpy.hcpn.hcpn_imp`)  
2. **`HCPNGraphViz` Visualizer** (`cpnpy.visualization.hcpn`)

Below, we discuss these in detail.

---

## 1. Core Concepts of Hierarchical Petri Nets

A **Hierarchical Colored Petri Net** consists of **multiple modules**, where each module is a standard `CPN` in `cpnpy`. The hierarchy arises from **substitution transitions** in a parent module referencing a child module (submodule).

### 1.1 Modules
- Each **module** is just a `CPN`:
  - Has its own places, transitions, arcs, and optional guards/delays.
  - Can be simulated on its own if desired.

### 1.2 Substitution Transition
- A **substitution transition** in a parent module is one that, instead of firing tokens via normal arcs, *delegates* token processing to a **child module** (another `CPN`).
- Parent transitions designated for substitution have no direct effect in the parent module; rather, the tokens “descend” into the child module.  
- After processing in the child module, the tokens can eventually “return” to the parent module (typically via additional arcs or port-place bindings).

### 1.3 Fusion Sets (Optional)
- **Fusion sets** allow merging multiple places across modules into a single *logical* place, so they share the same marking. 
- For example, if `PlaceX` in Module A and `PlaceY` in Module B are fused, adding a token to either place makes it available to transitions referencing **both** places. 
- Fusion sets are optional but are especially helpful when multiple modules need to share common data states seamlessly.

---

## 2. The `HCPN` Class

The `HCPN` class (found in [`cpnpy.hcpn.hcpn_imp`](./cpnpy/hcpn/hcpn_imp.py)) coordinates these hierarchical relationships.  

**Key Methods:**
- `add_module(name: str, cpn: CPN)`:  
  Register a named sub-CPN (module). For instance, `hcpn.add_module("A", cpn_A)`.
- `add_substitution(parent_module_name: str, sub_transition_name: str, submodule_name: str)`:  
  Indicate that the transition `sub_transition_name` in `parent_module_name` is a **substitution transition** referencing `submodule_name`.
  ```python
  # Example:
  hcpn.add_substitution("A", "T_ASub", "B")
  ```
- `get_module(name: str) -> Optional[CPN]`:  
  Retrieve a previously added module by name.
- `get_substitution_target(parent_module_name: str, sub_transition_name: str) -> Optional[str]`:  
  Query which module a given substitution transition points to.

**Data Structures Internally:**
- `self.modules`: A dictionary storing all the named modules (`CPN` objects).
- `self.substitutions`: A dictionary mapping `(parent_module, substitution_transition)` -> `child_module`.

You can also imagine an extension (not shown here) for:
- `add_fusion_set([...])`: to specify place names that share the same marking across modules.

### 2.1 Example Hierarchical Setup

Below is a simplified snippet (adapted from the code in [`hcpn_imp.py`](./cpnpy/hcpn/hcpn_imp.py)):

```python
from cpnpy.cpn.cpn_imp import *
from cpnpy.hcpn.hcpn_imp import HCPN

# Suppose we have two modules: a parent (A) and a child (B).
# Each is a standard CPN.

cpn_A = CPN()
pA = Place("P_A", int_set)
tASub = Transition("T_ASub")  # This will be a substitution transition
cpn_A.add_place(pA)
cpn_A.add_transition(tASub)

cpn_B = CPN()
pB = Place("P_B", int_set)
tB = Transition("T_B", guard="x >= 0", variables=["x"], transition_delay=2)
cpn_B.add_place(pB)
cpn_B.add_transition(tB)

# Build HCPN
hcpn = HCPN()
hcpn.add_module("A", cpn_A)
hcpn.add_module("B", cpn_B)

# Indicate that A's T_ASub references (substitutes) module B
hcpn.add_substitution("A", "T_ASub", "B")
```

In a real scenario, you would also link arcs that define how tokens enter or exit this substitution transition and how they travel into or out of the submodule’s places.

---

## 3. Visualizing an HCPN

`cpnpy` provides a specialized visualizer, **`HCPNGraphViz`**, located in [`cpnpy.visualization.hcpn`](./cpnpy/visualization/hcpn.py). It leverages Graphviz to display each module as a separate subgraph (cluster) and show the **dashed connections** from a parent’s substitution transition to the child module’s transitions.

### 3.1 The `HCPNGraphViz` Class

```python
class HCPNGraphViz:
    def apply(self, hcpn: HCPN, markings: Dict[str, Marking], format: str = "pdf") -> "HCPNGraphViz":
        ...
    
    def view(self):
        ...
    
    def save(self, filename: str):
        ...
```

- **`apply(hcpn, markings, format="pdf")`:**  
  - Takes the `HCPN` object plus a dictionary of markings for each module.
  - Produces an internal Graphviz `Digraph` object with one subgraph per module.
  - Draws places, transitions, arcs, and special color-coding for substitution transitions.  
  - Optionally include the current tokens (from the `Marking`) in each place’s label.
- **`view()`**: Opens the rendered diagram in your system’s default viewer (useful during development).  
- **`save(filename)`**: Renders the diagram to a file (PDF, PNG, etc., depending on `format`).

### 3.2 Example: Building and Visualizing a Multi-Level HCPN

Below is an example (excerpted from [`cpnpy.visualization.hcpn`](./cpnpy/visualization/hcpn.py)) showing how you might create a four-module HCPN (`A`, `B`, `C`, `D`) with nested substitution transitions, then visualize it:

```python
from cpnpy.cpn.cpn_imp import CPN, Place, Transition, Arc, Marking
from cpnpy.cpn.colorsets import ColorSetParser
from cpnpy.hcpn.hcpn_imp import HCPN
from cpnpy.visualization.hcpn import HCPNGraphViz

# 1) Define color sets
cs_definitions = "colset INT = int timed;"
parser = ColorSetParser()
colorsets = parser.parse_definitions(cs_definitions)
int_set = colorsets["INT"]

# 2) Build modules (A, B, C, D) as standard CPNs

# (a) Module D
cpn_D = CPN()
pD_in = Place("P_D_in", int_set)
pD_out = Place("P_D_out", int_set)
tD = Transition("T_D", variables=["d"], guard="d >= 0", transition_delay=1)
cpn_D.add_place(pD_in)
cpn_D.add_place(pD_out)
cpn_D.add_transition(tD)
cpn_D.add_arc(Arc(pD_in, tD, "d"))
cpn_D.add_arc(Arc(tD, pD_out, "d+5"))

# (b) Module C
cpn_C = CPN()
pC_in = Place("P_C_in", int_set)
pC_mid = Place("P_C_mid", int_set)
pC_out = Place("P_C_out", int_set)
tC = Transition("T_C", variables=["c"], guard="c < 100", transition_delay=0)
tCSub = Transition("T_CSub", variables=["c2"])  # sub transition references D
cpn_C.add_place(pC_in)
cpn_C.add_place(pC_mid)
cpn_C.add_place(pC_out)
cpn_C.add_transition(tC)
cpn_C.add_transition(tCSub)
cpn_C.add_arc(Arc(pC_in, tC, "c"))
cpn_C.add_arc(Arc(tC, pC_mid, "c+10"))
cpn_C.add_arc(Arc(pC_mid, tCSub, "c2"))
cpn_C.add_arc(Arc(tCSub, pC_out, "c2*2"))

# (c) Module B
cpn_B = CPN()
pB_in = Place("P_B_in", int_set)
pB_pass = Place("P_B_pass", int_set)
tB = Transition("T_B", variables=["b"], guard="b >= 0", transition_delay=2)
tBSub = Transition("T_BSub", variables=["b2"])  # sub transition references C
cpn_B.add_place(pB_in)
cpn_B.add_place(pB_pass)
cpn_B.add_transition(tB)
cpn_B.add_transition(tBSub)
cpn_B.add_arc(Arc(pB_in, tB, "b"))
cpn_B.add_arc(Arc(tB, pB_pass, "b+1"))
cpn_B.add_arc(Arc(pB_pass, tBSub, "b2"))
cpn_B.add_arc(Arc(tBSub, pB_in, "b2-5"))  # loop back for demonstration

# (d) Module A
cpn_A = CPN()
pA_start = Place("P_A_start", int_set)
pA_mid = Place("P_A_mid", int_set)
pA_fused = Place("P_A_fused", int_set)
tA = Transition("T_A", variables=["a"], guard="a >= 0", transition_delay=0)
tASub = Transition("T_ASub", variables=["a2"])  # sub transition references B
cpn_A.add_place(pA_start)
cpn_A.add_place(pA_mid)
cpn_A.add_place(pA_fused)
cpn_A.add_transition(tA)
cpn_A.add_transition(tASub)
cpn_A.add_arc(Arc(pA_start, tA, "a"))
cpn_A.add_arc(Arc(tA, pA_fused, "a*2"))
cpn_A.add_arc(Arc(pA_fused, tASub, "a2"))
cpn_A.add_arc(Arc(tASub, pA_mid, "a2+3"))

# 3) Combine into an HCPN
hcpn = HCPN()
hcpn.add_module("A", cpn_A)
hcpn.add_module("B", cpn_B)
hcpn.add_module("C", cpn_C)
hcpn.add_module("D", cpn_D)

# Define the substitution hierarchy
hcpn.add_substitution("A", "T_ASub", "B")
hcpn.add_substitution("B", "T_BSub", "C")
hcpn.add_substitution("C", "T_CSub", "D")

# 4) Create Markings (tokens) for each module if desired
marking_A = Marking()
marking_A.set_tokens("P_A_start", [0, 10, 20])
marking_B = Marking()
marking_C = Marking()
marking_D = Marking()

markings_dict = {
  "A": marking_A,
  "B": marking_B,
  "C": marking_C,
  "D": marking_D
}

# 5) Visualize
viz = HCPNGraphViz().apply(hcpn, markings_dict, format="pdf")

# Open a viewer (comment out in headless environments):
viz.view()

# Or save to a file
viz.save("my_hcpn_hierarchy")
```

When rendered, you’ll see:
- Each module (`A`, `B`, `C`, `D`) in its own subgraph (“cluster”).
- **Substitution transitions** colored differently (typically orange).
- **Dashed edges** from a parent’s substitution transition to the child’s transitions, indicating the hierarchy.

---
