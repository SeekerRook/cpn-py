from abc import ABC, abstractmethod
from collections import Counter
from typing import Any, Dict, List, Optional, Union

# -----------------------------------------------------------------------------------
# ColorSets
# -----------------------------------------------------------------------------------
class ColorSet(ABC):
    @abstractmethod
    def is_member(self, value: Any) -> bool:
        pass

class IntegerColorSet(ColorSet):
    def is_member(self, value: Any) -> bool:
        return isinstance(value, int)

    def __repr__(self):
        return "IntegerColorSet"

class StringColorSet(ColorSet):
    def is_member(self, value: Any) -> bool:
        return isinstance(value, str)

    def __repr__(self):
        return "StringColorSet"

class ProductColorSet(ColorSet):
    def __init__(self, cs1: ColorSet, cs2: ColorSet):
        self.cs1 = cs1
        self.cs2 = cs2

    def is_member(self, value: Any) -> bool:
        if not isinstance(value, tuple) or len(value) != 2:
            return False
        return self.cs1.is_member(value[0]) and self.cs2.is_member(value[1])

    def __repr__(self):
        return f"ProductColorSet({repr(self.cs1)}, {repr(self.cs2)})"


# -----------------------------------------------------------------------------------
# Token, Multiset, Marking
# -----------------------------------------------------------------------------------
class Token:
    def __init__(self, value: Any):
        self.value = value

    def __repr__(self):
        return f"Token({self.value})"

class Multiset:
    def __init__(self, tokens: Optional[List[Token]] = None):
        if tokens is None:
            tokens = []
        self._counter = Counter([t.value for t in tokens])

    def add(self, token_value: Any, count: int = 1):
        self._counter[token_value] += count

    def remove(self, token_value: Any, count: int = 1):
        if self._counter[token_value] < count:
            raise ValueError("Not enough tokens to remove.")
        self._counter[token_value] -= count
        if self._counter[token_value] <= 0:
            del self._counter[token_value]

    def __le__(self, other: 'Multiset') -> bool:
        for val, cnt in self._counter.items():
            if other._counter[val] < cnt:
                return False
        return True

    def __add__(self, other: 'Multiset') -> 'Multiset':
        new_ms = Multiset()
        new_ms._counter = self._counter + other._counter
        return new_ms

    def __sub__(self, other: 'Multiset') -> 'Multiset':
        new_ms = Multiset()
        for val in self._counter:
            diff = self._counter[val] - other._counter[val]
            if diff > 0:
                new_ms._counter[val] = diff
        return new_ms

    def __repr__(self):
        items_str = ", ".join([f"{val}*{cnt}" if cnt > 1 else str(val)
                               for val, cnt in self._counter.items()])
        return f"{{{items_str}}}"

class Marking:
    def __init__(self):
        self._marking: Dict[str, Multiset] = {}

    def set_tokens(self, place_name: str, tokens: List[Any]):
        self._marking[place_name] = Multiset([Token(v) for v in tokens])

    def add_tokens(self, place_name: str, token_values: List[Any]):
        ms = self._marking.get(place_name, Multiset())
        for v in token_values:
            ms.add(v)
        self._marking[place_name] = ms

    def remove_tokens(self, place_name: str, token_values: List[Any]):
        ms = self._marking.get(place_name, Multiset())
        for v in token_values:
            ms.remove(v)
        self._marking[place_name] = ms

    def get_multiset(self, place_name: str) -> Multiset:
        return self._marking.get(place_name, Multiset())

    def __repr__(self):
        # Provide a readable representation of the current marking.
        # Example: Marking:
        #  P_Int: {12, 5}
        #  P_Pair: {(12, 'hello')}
        lines = ["Marking:"]
        for place, ms in self._marking.items():
            lines.append(f"  {place}: {ms}")
        if len(lines) == 1:
            lines.append("  (empty)")
        return "\n".join(lines)


# -----------------------------------------------------------------------------------
# ColorSetParser
# -----------------------------------------------------------------------------------
class ColorSetParser:
    """
    A parser for a DSL that defines color sets.
    Grammar:
      definition := "colset" NAME "=" type ";"
      type := "int" | "string" | NAME | "product(" type "," type ")"
    """
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

        cs = self._parse_type(type_str)
        self.colorsets[name] = cs

    def _parse_type(self, type_str: str) -> ColorSet:
        # Base cases
        if type_str == "int":
            return IntegerColorSet()
        if type_str == "string":
            return StringColorSet()

        # product type
        if type_str.startswith("product(") and type_str.endswith(")"):
            inner = type_str[len("product("):-1].strip()
            comma_index = self._find_comma_at_top_level(inner)
            if comma_index == -1:
                raise ValueError("Invalid product definition: must have two types separated by a comma.")
            type1_str = inner[:comma_index].strip()
            type2_str = inner[comma_index+1:].strip()
            cs1 = self._parse_type(type1_str)
            cs2 = self._parse_type(type2_str)
            return ProductColorSet(cs1, cs2)

        # reference to an existing color set
        if type_str in self.colorsets:
            return self.colorsets[type_str]

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
# Place, Transition, Arc, CPN
# -----------------------------------------------------------------------------------
class Place:
    def __init__(self, name: str, colorset: ColorSet):
        self.name = name
        self.colorset = colorset

    def __repr__(self):
        return f"Place(name='{self.name}', colorset={repr(self.colorset)})"

class Transition:
    def __init__(self, name: str, guard: Optional[str] = None, variables: Optional[List[str]] = None):
        self.name = name
        self.guard_expr = guard
        self.variables = variables if variables else []

    def evaluate_guard(self, binding: Dict[str, Any]) -> bool:
        if self.guard_expr is None:
            return True
        return bool(eval(self.guard_expr, {}, binding))

    def __repr__(self):
        guard_str = self.guard_expr if self.guard_expr is not None else "None"
        vars_str = ", ".join(self.variables) if self.variables else "None"
        return f"Transition(name='{self.name}', guard='{guard_str}', variables=[{vars_str}])"

class Arc:
    def __init__(self, source: Union[Place, Transition], target: Union[Place, Transition], expression: str):
        self.source = source
        self.target = target
        self.expression = expression

    def evaluate(self, binding: Dict[str, Any]) -> List[Any]:
        val = eval(self.expression, {}, binding)
        if isinstance(val, list):
            return val
        else:
            return [val]

    def __repr__(self):
        src_name = self.source.name if isinstance(self.source, Place) else self.source.name
        tgt_name = self.target.name if isinstance(self.target, Place) else self.target.name
        return f"Arc(source='{src_name}', target='{tgt_name}', expr='{self.expression}')"

class CPN:
    def __init__(self):
        self.places: List[Place] = []
        self.transitions: List[Transition] = []
        self.arcs: List[Arc] = []
        self.initial_marking = Marking()

    def add_place(self, place: Place, initial_tokens: Optional[List[Any]] = None):
        self.places.append(place)
        if initial_tokens is None:
            initial_tokens = []
        valid_tokens = [t for t in initial_tokens if place.colorset.is_member(t)]
        self.initial_marking.set_tokens(place.name, valid_tokens)

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

    def is_enabled(self, t: Transition, binding: Dict[str, Any]) -> bool:
        if not t.evaluate_guard(binding):
            return False
        for arc in self.get_input_arcs(t):
            required_values = arc.evaluate(binding)
            place_marking = self.initial_marking.get_multiset(arc.source.name)
            required_ms = Multiset([Token(v) for v in required_values])
            if not required_ms._counter <= place_marking._counter:
                return False
        return True

    def fire_transition(self, t: Transition, binding: Dict[str, Any]):
        if not self.is_enabled(t, binding):
            raise RuntimeError(f"Transition {t.name} is not enabled under the given binding.")

        for arc in self.get_input_arcs(t):
            required_values = arc.evaluate(binding)
            self.initial_marking.remove_tokens(arc.source.name, required_values)

        for arc in self.get_output_arcs(t):
            produced_values = arc.evaluate(binding)
            self.initial_marking.add_tokens(arc.target.name, produced_values)

    def __repr__(self):
        places_str = "\n    ".join(repr(p) for p in self.places)
        transitions_str = "\n    ".join(repr(t) for t in self.transitions)
        arcs_str = "\n    ".join(repr(a) for a in self.arcs)
        marking_str = repr(self.initial_marking)
        return (f"CPN(\n  Places:\n    {places_str}\n\n"
                f"  Transitions:\n    {transitions_str}\n\n"
                f"  Arcs:\n    {arcs_str}\n\n"
                f"  {marking_str}\n)")

# -----------------------------------------------------------------------------------
# Example Usage
# -----------------------------------------------------------------------------------
if __name__ == "__main__":
    cs_definitions = """
    colset INT = int;
    colset STRING = string;
    colset PAIR = product(INT, STRING);
    """

    parser = ColorSetParser()
    colorsets = parser.parse_definitions(cs_definitions)

    int_set = colorsets["INT"]
    pair_set = colorsets["PAIR"]

    p_int = Place("P_Int", int_set)
    p_pair = Place("P_Pair", pair_set)
    t = Transition("T", guard="x > 10", variables=["x"])

    cpn = CPN()
    cpn.add_place(p_int, initial_tokens=[5, 12])  # P_Int starts with tokens 5 and 12
    cpn.add_place(p_pair)  # empty
    cpn.add_transition(t)

    cpn.add_arc(Arc(p_int, t, "x"))
    cpn.add_arc(Arc(t, p_pair, "(x, 'hello')"))

    print(cpn)

    binding = {"x": 5}
    print("Is T enabled with x=5?", cpn.is_enabled(t, binding))

    binding = {"x": 12}
    print("Is T enabled with x=12?", cpn.is_enabled(t, binding))
    cpn.fire_transition(t, binding)

    print(cpn)
