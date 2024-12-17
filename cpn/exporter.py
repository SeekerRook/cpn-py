from abc import ABC, abstractmethod
from collections import Counter
from typing import Any, Dict, List, Optional, Union
import json
import os

# -----------------------------------------------------------------------------------
# ColorSets with Timed Support
# -----------------------------------------------------------------------------------
class ColorSet(ABC):
    def __init__(self, timed: bool = False):
        self.timed = timed

    @abstractmethod
    def is_member(self, value: Any) -> bool:
        pass

    # We'll add equality and hash so we can store and compare sets in dictionaries.
    def __eq__(self, other):
        if type(self) != type(other):
            return False
        # Compare internal structure
        if isinstance(self, IntegerColorSet):
            return self.timed == other.timed
        if isinstance(self, StringColorSet):
            return self.timed == other.timed
        if isinstance(self, ProductColorSet):
            return self.timed == other.timed and self.cs1 == other.cs1 and self.cs2 == other.cs2
        return False

    def __hash__(self):
        if isinstance(self, IntegerColorSet):
            return hash(("IntegerColorSet", self.timed))
        if isinstance(self, StringColorSet):
            return hash(("StringColorSet", self.timed))
        if isinstance(self, ProductColorSet):
            return hash(("ProductColorSet", self.cs1, self.cs2, self.timed))
        return hash(id(self))  # Fallback, should not happen ideally


class IntegerColorSet(ColorSet):
    def is_member(self, value: Any) -> bool:
        return isinstance(value, int)

    def __repr__(self):
        timed_str = " timed" if self.timed else ""
        return f"IntegerColorSet{timed_str}"


class StringColorSet(ColorSet):
    def is_member(self, value: Any) -> bool:
        return isinstance(value, str)

    def __repr__(self):
        timed_str = " timed" if self.timed else ""
        return f"StringColorSet{timed_str}"


class ProductColorSet(ColorSet):
    def __init__(self, cs1: ColorSet, cs2: ColorSet, timed: bool = False):
        super().__init__(timed=timed)
        self.cs1 = cs1
        self.cs2 = cs2

    def is_member(self, value: Any) -> bool:
        if not isinstance(value, tuple) or len(value) != 2:
            return False
        return self.cs1.is_member(value[0]) and self.cs2.is_member(value[1])

    def __repr__(self):
        timed_str = " timed" if self.timed else ""
        return f"ProductColorSet({repr(self.cs1)}, {repr(self.cs2)}){timed_str}"


# -----------------------------------------------------------------------------------
# Token with Time
# -----------------------------------------------------------------------------------
class Token:
    def __init__(self, value: Any, timestamp: int = 0):
        self.value = value
        self.timestamp = timestamp  # For timed tokens

    def __repr__(self):
        if self.timestamp != 0:
            return f"Token({self.value}, t={self.timestamp})"
        return f"Token({self.value})"


class Multiset:
    def __init__(self, tokens: Optional[List[Token]] = None):
        if tokens is None:
            tokens = []
        self.tokens = tokens

    def add(self, token_value: Any, timestamp: int = 0, count: int = 1):
        for _ in range(count):
            self.tokens.append(Token(token_value, timestamp))

    def remove(self, token_value: Any, count: int = 1):
        matching = [t for t in self.tokens if t.value == token_value]
        if len(matching) < count:
            raise ValueError("Not enough tokens to remove.")
        matching.sort(key=lambda x: x.timestamp, reverse=True)
        to_remove = matching[:count]
        for tr in to_remove:
            self.tokens.remove(tr)

    def count_value(self, token_value: Any) -> int:
        return sum(1 for t in self.tokens if t.value == token_value)

    def __le__(self, other: 'Multiset') -> bool:
        self_counts = Counter(t.value for t in self.tokens)
        other_counts = Counter(t.value for t in other.tokens)
        for val, cnt in self_counts.items():
            if other_counts[val] < cnt:
                return False
        return True

    def __add__(self, other: 'Multiset') -> 'Multiset':
        return Multiset(self.tokens + other.tokens)

    def __sub__(self, other: 'Multiset') -> 'Multiset':
        result = Multiset(self.tokens[:])
        for t in other.tokens:
            result.remove(t.value, 1)
        return result

    def __repr__(self):
        items_str = ", ".join(str(t) for t in self.tokens)
        return f"{{{items_str}}}"


# -----------------------------------------------------------------------------------
# Marking with Global Clock
# -----------------------------------------------------------------------------------
class Marking:
    def __init__(self):
        self._marking: Dict[str, Multiset] = {}
        self.global_clock = 0  # Time support

    def set_tokens(self, place_name: str, tokens: List[Any], timestamps: Optional[List[int]] = None):
        if timestamps is None:
            timestamps = [0]*len(tokens)
        self._marking[place_name] = Multiset([Token(v, ts) for v, ts in zip(tokens, timestamps)])

    def add_tokens(self, place_name: str, token_values: List[Any], timestamp: int = 0):
        ms = self._marking.get(place_name, Multiset())
        for v in token_values:
            ms.add(v, timestamp=timestamp)
        self._marking[place_name] = ms

    def remove_tokens(self, place_name: str, token_values: List[Any]):
        ms = self._marking.get(place_name, Multiset())
        for v in token_values:
            ms.remove(v)
        self._marking[place_name] = ms

    def get_multiset(self, place_name: str) -> Multiset:
        return self._marking.get(place_name, Multiset())

    def __repr__(self):
        lines = [f"Marking (global_clock={self.global_clock}):"]
        for place, ms in self._marking.items():
            lines.append(f"  {place}: {ms}")
        if len(lines) == 1:
            lines.append("  (empty)")
        return "\n".join(lines)


# -----------------------------------------------------------------------------------
# ColorSetParser with Timed Support
# -----------------------------------------------------------------------------------
class ColorSetParser:
    def __init__(self):
        self.colorsets: Dict[str, ColorSet] = {}

    def parse_definitions(self, text: str) -> Dict[str, ColorSet]:
        lines = text.strip().splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            self._parse_line(line)
        return self.colorsets

    def _parse_line(self, line: str):
        if not line.endswith(";"):
            raise ValueError("Color set definition must end with a semicolon.")
        line = line[:-1].strip()  # remove trailing ";"
        if not line.startswith("colset "):
            raise ValueError("Color set definition must start with 'colset'.")
        line = line[len("colset "):].strip()
        parts = line.split("=", 1)
        if len(parts) != 2:
            raise ValueError("Invalid color set definition format.")
        name = parts[0].strip()
        type_str = parts[1].strip()

        # Check for "timed" keyword at the end
        timed = False
        if type_str.endswith("timed"):
            timed = True
            type_str = type_str[:-5].strip()

        cs = self._parse_type(type_str, timed)
        self.colorsets[name] = cs

    def _parse_type(self, type_str: str, timed: bool) -> ColorSet:
        if type_str == "int":
            return IntegerColorSet(timed=timed)
        if type_str == "string":
            return StringColorSet(timed=timed)

        if type_str.startswith("product(") and type_str.endswith(")"):
            inner = type_str[len("product("):-1].strip()
            comma_index = self._find_comma_at_top_level(inner)
            if comma_index == -1:
                raise ValueError("Invalid product definition: must have two types separated by a comma.")
            type1_str = inner[:comma_index].strip()
            type2_str = inner[comma_index + 1:].strip()

            cs1 = self._parse_type(type1_str, False)
            cs2 = self._parse_type(type2_str, False)
            return ProductColorSet(cs1, cs2, timed=timed)

        if type_str in self.colorsets:
            base_cs = self.colorsets[type_str]
            # If current definition is timed, ensure the base is also timed
            base_cs.timed = base_cs.timed or timed
            return base_cs

        raise ValueError(f"Unknown type definition or reference: {type_str}")

    def _find_comma_at_top_level(self, s: str) -> int:
        level = 0
        for i, ch in enumerate(s):
            if ch == '(':
                level += 1
            elif ch == ')':
                level -= 1
            elif ch == ',' and level == 0:
                return i
        return -1


# -----------------------------------------------------------------------------------
# EvaluationContext
# -----------------------------------------------------------------------------------
class EvaluationContext:
    def __init__(self, user_code: Optional[str] = None):
        self.env = {}
        if user_code is not None:
            exec(user_code, self.env)
            # Store original code for exporting if needed
            self.env['__original_user_code__'] = user_code

    def evaluate_guard(self, guard_expr: Optional[str], binding: Dict[str, Any]) -> bool:
        if guard_expr is None:
            return True
        return bool(eval(guard_expr, self.env, binding))

    def evaluate_arc(self, arc_expr: str, binding: Dict[str, Any]) -> (List[Any], int):
        delay = 0
        if "@+" in arc_expr:
            parts = arc_expr.split('@+')
            expr_part = parts[0].strip()
            delay_part = parts[1].strip()
            val = eval(expr_part, self.env, binding)
            delay = eval(delay_part, self.env, binding)
        else:
            val = eval(arc_expr, self.env, binding)

        if isinstance(val, list):
            return val, delay
        return [val], delay


# -----------------------------------------------------------------------------------
# Place, Transition, Arc, CPN with Time
# -----------------------------------------------------------------------------------
class Place:
    def __init__(self, name: str, colorset: ColorSet):
        self.name = name
        self.colorset = colorset

    def __repr__(self):
        return f"Place(name='{self.name}', colorset={repr(self.colorset)})"


class Transition:
    def __init__(self, name: str, guard: Optional[str] = None, variables: Optional[List[str]] = None, transition_delay: int = 0):
        self.name = name
        self.guard_expr = guard
        self.variables = variables if variables else []
        self.transition_delay = transition_delay

    def __repr__(self):
        guard_str = self.guard_expr if self.guard_expr is not None else "None"
        vars_str = ", ".join(self.variables) if self.variables else "None"
        return f"Transition(name='{self.name}', guard='{guard_str}', variables=[{vars_str}], delay={self.transition_delay})"


class Arc:
    def __init__(self, source: Union[Place, Transition], target: Union[Place, Transition], expression: str):
        self.source = source
        self.target = target
        self.expression = expression

    def __repr__(self):
        src_name = self.source.name if isinstance(self.source, Place) else self.source.name
        tgt_name = self.target.name if isinstance(self.target, Place) else self.target.name
        return f"Arc(source='{src_name}', target='{tgt_name}', expr='{self.expression}')"


class CPN:
    def __init__(self):
        self.places: List[Place] = []
        self.transitions: List[Transition] = []
        self.arcs: List[Arc] = []

    def add_place(self, place: Place):
        self.places.append(place)

    def add_transition(self, transition: Transition):
        self.transitions.append(transition)

    def add_arc(self, arc: Arc):
        self.arcs.append(arc)

    def get_place_by_name(self, name: str) -> Optional[Place]:
        for p in self.places:
            if p.name == name:
                return p
        return None

    def get_transition_by_name(self, name: str) -> Optional[Transition]:
        for t in self.transitions:
            if t.name == name:
                return t
        return None

    def get_input_arcs(self, t: Transition) -> List[Arc]:
        return [a for a in self.arcs if isinstance(a.source, Place) and a.target == t]

    def get_output_arcs(self, t: Transition) -> List[Arc]:
        return [a for a in self.arcs if a.source == t and isinstance(a.target, Place)]

    def is_enabled(self, t: Transition, marking: Marking, context: EvaluationContext,
                   binding: Optional[Dict[str, Any]] = None) -> bool:
        if binding is None:
            binding = self._find_binding(t, marking, context)
            if binding is None:
                return False
        return self._check_enabled_with_binding(t, marking, context, binding)

    def fire_transition(self, t: Transition, marking: Marking, context: EvaluationContext,
                        binding: Optional[Dict[str, Any]] = None):
        if binding is None:
            binding = self._find_binding(t, marking, context)
            if binding is None:
                raise RuntimeError(f"No valid binding found for transition {t.name}.")
        if not self._check_enabled_with_binding(t, marking, context, binding):
            raise RuntimeError(f"Transition {t.name} is not enabled under the found binding.")

        # Remove tokens
        for arc in self.get_input_arcs(t):
            values, _ = context.evaluate_arc(arc.expression, binding)
            marking.remove_tokens(arc.source.name, values)

        # Add tokens with proper timestamps
        for arc in self.get_output_arcs(t):
            values, arc_delay = context.evaluate_arc(arc.expression, binding)
            for v in values:
                place = arc.target
                new_timestamp = marking.global_clock + t.transition_delay + arc_delay
                if place.colorset.timed:
                    marking.add_tokens(place.name, [v], timestamp=new_timestamp)
                else:
                    marking.add_tokens(place.name, [v], timestamp=0)

    def _check_enabled_with_binding(self, t: Transition, marking: Marking, context: EvaluationContext,
                                    binding: Dict[str, Any]) -> bool:
        if not context.evaluate_guard(t.guard_expr, binding):
            return False
        # Check input arcs and timestamps
        for arc in self.get_input_arcs(t):
            values, _ = context.evaluate_arc(arc.expression, binding)
            place_marking = marking.get_multiset(arc.source.name)
            for val in values:
                ready_tokens = [tok for tok in place_marking.tokens if tok.value == val and tok.timestamp <= marking.global_clock]
                if len(ready_tokens) < values.count(val):
                    return False
        return True

    def _find_binding(self, t: Transition, marking: Marking, context: EvaluationContext) -> Optional[Dict[str, Any]]:
        variables = t.variables
        input_arcs = self.get_input_arcs(t)

        # Gather candidate token values
        token_pool = []
        for arc in input_arcs:
            place_tokens = marking.get_multiset(arc.source.name).tokens
            candidate_tokens = [tok for tok in place_tokens if tok.timestamp <= marking.global_clock]
            token_pool.extend([tok.value for tok in candidate_tokens])

        return self._backtrack_binding(variables, token_pool, context, t, marking, {})

    def _backtrack_binding(self, variables: List[str], token_pool: List[Any], context: EvaluationContext,
                           t: Transition, marking: Marking, partial_binding: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not variables:
            if self._check_enabled_with_binding(t, marking, context, partial_binding):
                return partial_binding
            return None

        var = variables[0]
        tried_values = set()
        for val in token_pool:
            if val in tried_values:
                continue
            tried_values.add(val)
            new_binding = dict(partial_binding)
            new_binding[var] = val
            res = self._backtrack_binding(variables[1:], token_pool, context, t, marking, new_binding)
            if res is not None:
                return res
        return None

    def advance_global_clock(self, marking: Marking):
        future_ts = []
        for ms in marking._marking.values():
            for tok in ms.tokens:
                if tok.timestamp > marking.global_clock:
                    future_ts.append(tok.timestamp)
        if future_ts:
            marking.global_clock = min(future_ts)

    def __repr__(self):
        places_str = "\n    ".join(repr(p) for p in self.places)
        transitions_str = "\n    ".join(repr(t) for t in self.transitions)
        arcs_str = "\n    ".join(repr(a) for a in self.arcs)
        return (f"CPN(\n  Places:\n    {places_str}\n\n"
                f"  Transitions:\n    {transitions_str}\n\n"
                f"  Arcs:\n    {arcs_str}\n)")


# -----------------------------------------------------------------------------------
# Exporter
# -----------------------------------------------------------------------------------
def generate_color_set_definitions(cpn: CPN):
    """
    Generate definitions for all distinct color sets used in the CPN.
    Returns:
      (colorset_to_name_map, name_to_definition_map)
    """
    colorset_to_name = {}
    name_to_def = {}

    def define_colorset(cs: ColorSet) -> str:
        # If already defined, return the existing name
        if cs in colorset_to_name:
            return colorset_to_name[cs]

        assigned_name = f"CS{len(colorset_to_name)}"
        colorset_to_name[cs] = assigned_name

        timed_str = " timed" if cs.timed else ""
        if isinstance(cs, IntegerColorSet):
            base_def = f"colset {assigned_name} = int{timed_str};"
        elif isinstance(cs, StringColorSet):
            base_def = f"colset {assigned_name} = string{timed_str};"
        elif isinstance(cs, ProductColorSet):
            cs1_name = define_colorset(cs.cs1)
            cs2_name = define_colorset(cs.cs2)
            base_def = f"colset {assigned_name} = product({cs1_name}, {cs2_name}){timed_str};"
        else:
            raise ValueError(f"Unknown ColorSet type: {cs}")

        name_to_def[assigned_name] = base_def
        return assigned_name

    for p in cpn.places:
        define_colorset(p.colorset)

    return colorset_to_name, name_to_def

def export_cpn_to_json(cpn: CPN, marking: Marking, context: Optional[EvaluationContext], output_json_path: str, output_py_path: Optional[str] = None):
    # Generate color set definitions
    cs_to_name, name_to_def = generate_color_set_definitions(cpn)

    # Places
    places_json = []
    for p in cpn.places:
        places_json.append({
            "name": p.name,
            "colorSet": cs_to_name[p.colorset]
        })

    # Transitions
    transitions_json = []
    for t in cpn.transitions:
        in_arcs = []
        out_arcs = []
        for arc in cpn.arcs:
            if arc.target == t and isinstance(arc.source, Place):
                in_arcs.append({
                    "place": arc.source.name,
                    "expression": arc.expression
                })
            elif arc.source == t and isinstance(arc.target, Place):
                out_arcs.append({
                    "place": arc.target.name,
                    "expression": arc.expression
                })

        t_json = {
            "name": t.name,
            "inArcs": in_arcs,
            "outArcs": out_arcs
        }
        if t.guard_expr is not None:
            t_json["guard"] = t.guard_expr
        if t.variables:
            t_json["variables"] = t.variables
        if t.transition_delay != 0:
            t_json["transitionDelay"] = t.transition_delay

        transitions_json.append(t_json)

    # Initial Marking
    initial_marking = {}
    for pname, ms in marking._marking.items():
        tokens = [tok.value for tok in ms.tokens]
        timestamps = [tok.timestamp for tok in ms.tokens]
        if any(ts != 0 for ts in timestamps):
            initial_marking[pname] = {
                "tokens": tokens,
                "timestamps": timestamps
            }
        else:
            initial_marking[pname] = {
                "tokens": tokens
            }

    # ColorSets as array of definitions
    sorted_defs = [name_to_def[n] for n in sorted(name_to_def.keys(), key=lambda x: int(x[2:]))]

    # Evaluation Context
    evaluation_context_val = None
    if context is not None:
        user_code = context.env.get('__original_user_code__', None)
        if user_code is not None and user_code.strip():
            # Check if user_code is a file
            if os.path.isfile(user_code):
                evaluation_context_val = user_code
            else:
                # Write inline code to file if specified
                if output_py_path is None:
                    output_py_path = "user_code_exported.py"
                with open(output_py_path, "w") as f:
                    f.write(user_code)
                evaluation_context_val = output_py_path
        else:
            # No user code
            evaluation_context_val = None
    else:
        evaluation_context_val = None

    final_json = {
        "colorSets": sorted_defs,
        "places": places_json,
        "transitions": transitions_json,
        "initialMarking": initial_marking,
        "evaluationContext": evaluation_context_val
    }

    with open(output_json_path, "w") as f:
        json.dump(final_json, f, indent=2)

    return final_json


# -----------------------------------------------------------------------------------
# Example Usage (for testing the exporter)
# -----------------------------------------------------------------------------------
if __name__ == "__main__":
    # Use multiline definition for color sets:
    cs_parser = ColorSetParser()
    cs_defs = cs_parser.parse_definitions("""\
colset INT = int timed;
colset STRING = string;
colset PAIR = product(INT, STRING) timed;
""")
    int_set = cs_defs["INT"]
    pair_set = cs_defs["PAIR"]

    p_int = Place("P_Int", int_set)
    p_pair = Place("P_Pair", pair_set)
    t = Transition("T", guard="x > 10", variables=["x"], transition_delay=2)
    cpn = CPN()
    cpn.add_place(p_int)
    cpn.add_place(p_pair)
    cpn.add_transition(t)
    cpn.add_arc(Arc(p_int, t, "x"))
    cpn.add_arc(Arc(t, p_pair, "(x, 'hello') @+5"))

    marking = Marking()
    marking.set_tokens("P_Int", [5, 12])

    # Fake evaluation context
    user_code = "def double(n): return n*2"
    context = EvaluationContext(user_code=user_code)

    # Export
    exported = export_cpn_to_json(cpn, marking, context, "cpn_export.json", "user_code_exported.py")
    print("Exported JSON:")
    print(json.dumps(exported, indent=2))
