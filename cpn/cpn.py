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
        if type_str == "int":
            return IntegerColorSet()
        if type_str == "string":
            return StringColorSet()

        if type_str.startswith("product(") and type_str.endswith(")"):
            inner = type_str[len("product("):-1].strip()
            comma_index = self._find_comma_at_top_level(inner)
            if comma_index == -1:
                raise ValueError("Invalid product definition: must have two types separated by a comma.")
            type1_str = inner[:comma_index].strip()
            type2_str = inner[comma_index + 1:].strip()
            cs1 = self._parse_type(type1_str)
            cs2 = self._parse_type(type2_str)
            return ProductColorSet(cs1, cs2)

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
# EvaluationContext
# -----------------------------------------------------------------------------------
class EvaluationContext:
    def __init__(self, user_code: Optional[str] = None):
        self.env = {}
        if user_code is not None:
            exec(user_code, self.env)

    def evaluate_guard(self, guard_expr: Optional[str], binding: Dict[str, Any]) -> bool:
        if guard_expr is None:
            return True
        return bool(eval(guard_expr, self.env, binding))

    def evaluate_arc(self, arc_expr: str, binding: Dict[str, Any]) -> List[Any]:
        val = eval(arc_expr, self.env, binding)
        if isinstance(val, list):
            return val
        return [val]


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

    def __repr__(self):
        guard_str = self.guard_expr if self.guard_expr is not None else "None"
        vars_str = ", ".join(self.variables) if self.variables else "None"
        return f"Transition(name='{self.name}', guard='{guard_str}', variables=[{vars_str}])"


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
            required_values = context.evaluate_arc(arc.expression, binding)
            marking.remove_tokens(arc.source.name, required_values)
        # Add tokens
        for arc in self.get_output_arcs(t):
            produced_values = context.evaluate_arc(arc.expression, binding)
            marking.add_tokens(arc.target.name, produced_values)

    def _check_enabled_with_binding(self, t: Transition, marking: Marking, context: EvaluationContext,
                                    binding: Dict[str, Any]) -> bool:
        if not context.evaluate_guard(t.guard_expr, binding):
            return False
        for arc in self.get_input_arcs(t):
            required_values = context.evaluate_arc(arc.expression, binding)
            place_marking = marking.get_multiset(arc.source.name)
            required_ms = Multiset([Token(v) for v in required_values])
            if not required_ms._counter <= place_marking._counter:
                return False
        return True

    def _find_binding(self, t: Transition, marking: Marking, context: EvaluationContext) -> Optional[Dict[str, Any]]:
        """
        Attempt to find a binding for the variables of t that enables it.
        We do a simple backtracking search over tokens in input places.
        """
        variables = t.variables
        input_arcs = self.get_input_arcs(t)

        # Gather all candidate token values from input places that match the arcs' variable usage.
        # This is tricky because arcs might not always have a direct variable-to-place mapping.
        # For a simple approach, we consider all tokens from all input places as potential candidates
        # for each variable.
        candidate_values = []

        # We attempt a general strategy:
        # 1. Collect all tokens from input places.
        # 2. We'll try to assign each variable a token from this pool that leads to a successful enabling.

        token_pool = []
        for arc in input_arcs:
            place_tokens = marking.get_multiset(arc.source.name)
            for val, cnt in place_tokens._counter.items():
                # add these token values 'cnt' times to the pool
                token_pool.extend([val] * cnt)

        # We now have a pool of token values. We'll try all combinations of assigning these values to the variables.
        # For efficiency, if a variable does not appear in arcs or guard, it can still be assigned any value,
        # but we might just pick from the pool arbitrarily.

        return self._backtrack_binding(variables, token_pool, context, t, marking, {})

    def _backtrack_binding(self, variables: List[str], token_pool: List[Any], context: EvaluationContext,
                           t: Transition, marking: Marking, partial_binding: Dict[str, Any]) -> Optional[
        Dict[str, Any]]:
        # If we've assigned all variables, check if enabled
        if not variables:
            # Check if enabled with this binding
            if self._check_enabled_with_binding(t, marking, context, partial_binding):
                return partial_binding
            return None

        var = variables[0]
        # Try assigning each token from token_pool to var
        # To reduce complexity, we could try unique token values.
        tried_values = set()
        for val in token_pool:
            if val in tried_values:
                continue
            tried_values.add(val)
            new_binding = dict(partial_binding)
            new_binding[var] = val
            # Check partial feasibility:
            # It's expensive to check full enabling at each step; we just proceed and hope final check passes.
            # For optimization, we could do partial checks here, but let's keep it simple.
            # Move on to next variable
            res = self._backtrack_binding(variables[1:], token_pool, context, t, marking, new_binding)
            if res is not None:
                return res
        return None

    def __repr__(self):
        places_str = "\n    ".join(repr(p) for p in self.places)
        transitions_str = "\n    ".join(repr(t) for t in self.transitions)
        arcs_str = "\n    ".join(repr(a) for a in self.arcs)
        return (f"CPN(\n  Places:\n    {places_str}\n\n"
                f"  Transitions:\n    {transitions_str}\n\n"
                f"  Arcs:\n    {arcs_str}\n)")


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

    # Create the CPN structure
    p_int = Place("P_Int", int_set)
    p_pair = Place("P_Pair", pair_set)
    t = Transition("T", guard="x > 10", variables=["x"])

    cpn = CPN()
    cpn.add_place(p_int)
    cpn.add_place(p_pair)
    cpn.add_transition(t)
    cpn.add_arc(Arc(p_int, t, "x"))
    cpn.add_arc(Arc(t, p_pair, "(x, 'hello')"))

    # Create a separate marking
    marking = Marking()
    marking.set_tokens("P_Int", [5, 12])  # Manage marking separately

    user_code = """
def double(n):
    return n*2
"""
    context = EvaluationContext(user_code=user_code)

    print(cpn)
    print(marking)

    print(cpn.is_enabled(t, marking, context, binding={"x": 5}))
    print(cpn.is_enabled(t, marking, context, binding={"x": 12}))

    # Check enabled without providing a binding
    print("Is T enabled without explicit binding?", cpn.is_enabled(t, marking, context))  # should find binding x=12

    # Fire the transition without providing a binding
    cpn.fire_transition(t, marking, context)
    print(marking)
