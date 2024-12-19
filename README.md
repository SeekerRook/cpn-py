# cpnpy

`cpnpy` is a Python-based library designed to simulate Colored Petri Nets (CPNs) with optional time semantics. It provides classes and functions to define places, transitions, arcs, and markings, along with color sets and evaluation contexts to express guards, arc expressions, and timed behavior.

**Key features include:**
- Defining color sets (including `int`, `real`, `string`, enumerated, and product types) with optional timing.
- Creating places and transitions, each associated with a specific color set and optional guard conditions.
- Specifying arcs with expressions and delays that determine how tokens move through the net.
- Managing tokens as multisets of timed or untimed values.
- Simulating CPN behavior: checking transition enabling, firing transitions, and advancing time.

---

## Installation

You can install `cpnpy` directly from source. If you have a proper `setup.py`, you could run:
```bash
pip install -e .
```

---

## Basic Concepts

### Color Sets

Color sets define the domain of values that tokens can take. They can be:
- **Integer, Real, and String sets**, optionally timed.
- **Enumerated sets**, like `{ 'red', 'green' }`.
- **Product sets**, such as `product(INT, STRING)`, optionally timed.

**Example:**
```python
from cpnpy.cpn.colorsets import ColorSetParser

cs_defs = """
colset INT = int timed;
colset STRING = string;
colset PAIR = product(INT, STRING) timed;
"""
parser = ColorSetParser()
colorsets = parser.parse_definitions(cs_defs)
int_set = colorsets["INT"]    # timed integer set
pair_set = colorsets["PAIR"]  # timed product of (INT, STRING)
```

### Places

A `Place` holds a multiset of tokens, each token conforming to the place's color set. If the color set is timed, the tokens will carry timestamps.

**Example:**
```python
from cpnpy.cpn.cpn_imp import Place

p_int = Place("P_Int", int_set)      # A place for timed integers
p_pair = Place("P_Pair", pair_set)   # A place for timed pairs (int, string)
```

### Markings

A `Marking` represents a state of the net, holding the current tokens in each place, as well as a global clock.

**Example:**
```python
from cpnpy.cpn.cpn_imp import Marking

marking = Marking()
marking.set_tokens("P_Int", [5, 12])  # Two integer tokens (5, 12) with timestamp = 0
print(marking)
# Marking (global_clock=0):
#   P_Int: {Token(5), Token(12)}
```

### Transitions and Guards

A `Transition` may have a guard expression and variables. When the transition fires, tokens are consumed from its input places and produced in its output places. Guards and arc expressions can refer to these variables.

**Example:**
```python
from cpnpy.cpn.cpn_imp import Transition

t = Transition("T",
               guard="x > 10",      # a Python expression evaluated with the binding {x: token_value}
               variables=["x"],
               transition_delay=2)  # delay after firing, affects token timestamps on output arcs
```

### Arcs and Expressions

Arcs connect places and transitions. Arc expressions determine which tokens are taken or produced. If timed arcs are used (e.g. `@+5`), produced tokens will have an additional delay.

**Example:**
```python
from cpnpy.cpn.cpn_imp import Arc

# Arc from place P_Int to transition T, consuming a token bound to variable x
arc_in = Arc(p_int, t, "x")

# Arc from transition T to place P_Pair, producing a token (x, 'hello') delayed by an additional 5 time units
arc_out = Arc(t, p_pair, "(x, 'hello') @+5")
```

### Putting It Together: The CPN

A `CPN` ties together places, transitions, and arcs.

**Example:**
```python
from cpnpy.cpn.cpn_imp import CPN, EvaluationContext

cpn = CPN()
cpn.add_place(p_int)
cpn.add_place(p_pair)
cpn.add_transition(t)
cpn.add_arc(arc_in)
cpn.add_arc(arc_out)

user_code = """
def double(n):
    return n * 2
"""
context = EvaluationContext(user_code=user_code)
```

---

## Simulation Steps

1. **Check if a Transition is Enabled**

   `is_enabled` checks if a transition can fire given the current marking and context. It tries to find a token binding that satisfies the guard and provides enough tokens.

   ```python
   print("Is T enabled with x=5?", cpn.is_enabled(t, marking, context, binding={"x": 5}))
   # False, since guard x > 10 fails for x=5
   print("Is T enabled with x=12?", cpn.is_enabled(t, marking, context, binding={"x": 12}))
   # True, since guard x > 10 succeeds for x=12
   ```

   If you don't provide a binding, `is_enabled` tries to find one automatically:
   ```python
   print("Is T enabled without explicit binding?", cpn.is_enabled(t, marking, context))
   # True (it finds x=12 as a suitable binding)
   ```

2. **Find All Possible Bindings**

   If multiple tokens can satisfy the guard and arc expressions, `_find_all_bindings` returns all valid bindings:
   
   ```python
   all_bindings = cpn._find_all_bindings(t, marking, context)
   print("All possible bindings for T:", all_bindings)
   # E.g. [{'x': 12}] if only the token 12 satisfies the guard.
   ```

3. **Firing a Transition**

   When a transition fires, it consumes tokens from input places and produces tokens in output places, updating their timestamps based on the transition and arc delays:
   
   ```python
   cpn.fire_transition(t, marking, context)
   print(marking)
   # Marking now has consumed the token 12 from P_Int and added a token to P_Pair with a proper timestamp.
   ```

4. **Advancing the Global Clock**

   The global clock in the marking can be advanced to the next available token timestamp. This models the passage of time:
   
   ```python
   cpn.advance_global_clock(marking)
   print("After advancing global clock:", marking.global_clock)
   # global_clock might now match the timestamp of the next future token.
   ```

---

## Minimal Example

```python
from cpnpy.cpn.cpn_imp import CPN, Place, Transition, Arc, Marking, EvaluationContext
from cpnpy.cpn.colorsets import ColorSetParser

# Define color sets
cs_defs = "colset INT = int timed;"
parser = ColorSetParser()
colorsets = parser.parse_definitions(cs_defs)
int_set = colorsets["INT"]

# Create places and a transition
p_in = Place("P_In", int_set)
p_out = Place("P_Out", int_set)
t = Transition("T", guard="x > 0", variables=["x"], transition_delay=1)

# Create arcs: consume 'x' from P_In, produce 'x+1' in P_Out after 2 time units
arc_in = Arc(p_in, t, "x")
arc_out = Arc(t, p_out, "double(x) @+2")

# Build the net
cpn = CPN()
cpn.add_place(p_in)
cpn.add_place(p_out)
cpn.add_transition(t)
cpn.add_arc(arc_in)
cpn.add_arc(arc_out)

# Create a marking
marking = Marking()
marking.set_tokens("P_In", [1, -1])  # both at time 0

# Evaluation context with a user-defined function
user_code = "def double(n): return n*2"
context = EvaluationContext(user_code=user_code)

print("Initial marking:")
print(marking)

# Check enabling
print("Is T enabled?", cpn.is_enabled(t, marking, context))
# True, because x=1 is a positive token.

# Fire the transition
cpn.fire_transition(t, marking, context)
print("After firing T:")
print(marking)
# Token (1) is consumed from P_In, token 2 (double(1)) is added to P_Out with timestamp = global_clock + 1 (transition_delay) + 2 (arc delay) = 3

# Advance time
cpn.advance_global_clock(marking)
print("After advancing clock:", marking.global_clock)
# global_clock = 3
```

---

## Importing a CPN from JSON

You can define your CPN in a JSON file and import it using `importer.py`. The JSON must follow the structure enforced by `files/validation.schema`.

**Example:**
```python
import json
from cpnpy.cpn.importer import import_cpn_from_json

with open("cpn_definition.json", "r") as f:
    data = json.load(f)

cpn, marking, context = import_cpn_from_json(data)

# Now 'cpn' is a CPN object, 'marking' is the initial marking, and 'context' is the evaluation context.
```

**Key Points:**
- The `colorSets` field in the JSON should be a list of color set definitions, each ending with a `;`.
- `places`, `transitions`, and `initialMarking` define the net structure and initial state.
- `evaluationContext` can specify a file path or inline code snippet for user-defined functions.

---

## Exporting a CPN to JSON

You can also export an existing CPN and marking to a JSON file that matches the schema. The `exporter.py` provides this functionality:

**Example:**
```python
from cpnpy.cpn.exporter import export_cpn_to_json

# Assuming you have a CPN, marking, and context objects as before
exported_json = export_cpn_to_json(cpn, marking, context, "cpn_exported.json", "user_code_exported.py")

# The exported_json dictionary will have all the data. 
# Additionally, the JSON will be written to "cpn_exported.json".
# If user code was embedded, it is exported to "user_code_exported.py".
```

---

## Validation Against the Schema

The JSON format is defined by `files/validation.schema`. You can use a JSON Schema validator (such as `jsonschema`) to ensure your input JSON is valid:

```bash
pip install jsonschema
```

**Example:**
```python
import json
import jsonschema

with open("cpn_definition.json") as f:
    data = json.load(f)
with open("files/validation.schema") as sf:
    schema = json.load(sf)

jsonschema.validate(instance=data, schema=schema)
print("JSON is valid!")
```

If the JSON is invalid, `jsonschema` will raise a `jsonschema.exceptions.ValidationError` with details.

---

---

## Additional Notes

- **Bindings and Guard Evaluation:** Guards and arc expressions are Python code snippets evaluated under a user-defined `EvaluationContext`. This allows integrating custom logic (functions, constants) into your CPN model.
- **Deep and Shallow Copying:** The classes implement `__copy__` and `__deepcopy__` to facilitate safe cloning of the CPN and marking states if needed.
- **Error Handling:** When tokens or bindings are insufficient to fire a transition, appropriate exceptions (e.g., `RuntimeError` or `ValueError`) are raised.

---

## Contributing and Feedback

Contributions, bug reports, and feature requests are welcome. Open an issue or submit a pull request to help improve `cpnpy`.
