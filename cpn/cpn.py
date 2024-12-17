from abc import ABC, abstractmethod
from collections import Counter
from typing import Any, Dict, List, Optional, Union

# -----------------------------------------------------------------------------------
# ColorSets with Timed Support
# -----------------------------------------------------------------------------------
class ColorSet(ABC):
    def __init__(self, timed: bool = False):
        self.timed = timed

    @abstractmethod
    def is_member(self, value: Any) -> bool:
        pass


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
        # We'll store a list of tokens (with timestamps)
        self.tokens = tokens

    def add(self, token_value: Any, timestamp: int = 0, count: int = 1):
        for _ in range(count):
            self.tokens.append(Token(token_value, timestamp))

    def remove(self, token_value: Any, count: int = 1):
        # Removing tokens can be tricky if timed. The occurrence rule states:
        # For tokens of the same color, we should consume the one with the largest timestamp.
        matching = [t for t in self.tokens if t.value == token_value]
        if len(matching) < count:
            raise ValueError("Not enough tokens to remove.")
        # Sort by timestamp descending, consume largest first.
        matching.sort(key=lambda x: x.timestamp, reverse=True)
        to_remove = matching[:count]
        for tr in to_remove:
            self.tokens.remove(tr)

    def count_value(self, token_value: Any) -> int:
        return sum(1 for t in self.tokens if t.value == token_value)

    def __le__(self, other: 'Multiset') -> bool:
        # For enabling checks (without considering exact timestamps),
        # we just ensure that for each value we need, other has at least that many.
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
            # If the top-level said timed, the product is timed.
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

    def evaluate_guard(self, guard_expr: Optional[str], binding: Dict[str, Any]) -> bool:
        if guard_expr is None:
            return True
        return bool(eval(guard_expr, self.env, binding))

    def evaluate_arc(self, arc_expr: str, binding: Dict[str, Any]) -> (List[Any], int):
        """
        Evaluate the arc expression. We now also check for time delays using @+ syntax.
        If found, separate the delay and return it along with the values.
        """
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
            values, _ = context.evaluate_arc(arc.expression, binding)
            marking.remove_tokens(arc.source.name, values)

        # Add tokens with proper timestamps
        for arc in self.get_output_arcs(t):
            values, arc_delay = context.evaluate_arc(arc.expression, binding)
            for v in values:
                place = arc.target
                ts = marking.global_clock + arc_delay
                # If target place is timed, use computed timestamp
                # If not timed, timestamp stays 0
                if place.colorset.timed:
                    marking.add_tokens(place.name, [v], timestamp=ts)
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
            # Check if we have enough ready tokens (timestamp <= global_clock)
            for val in values:
                ready_tokens = [tok for tok in place_marking.tokens if tok.value == val and tok.timestamp <= marking.global_clock]
                if len(ready_tokens) < values.count(val):
                    return False
        return True

    def _find_binding(self, t: Transition, marking: Marking, context: EvaluationContext) -> Optional[Dict[str, Any]]:
        variables = t.variables
        input_arcs = self.get_input_arcs(t)

        # Gather a pool of candidate token values from input places that are ready
        token_pool = []
        for arc in input_arcs:
            place_tokens = marking.get_multiset(arc.source.name).tokens
            candidate_tokens = [tok for tok in place_tokens if tok.timestamp <= marking.global_clock]
            token_pool.extend([t.value for t in candidate_tokens])

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
        """
        Advance the global_clock to the next earliest token timestamp that might enable a transition.
        If no such token exists, does nothing.
        """
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
# Example Usage (Timed)
# -----------------------------------------------------------------------------------
if __name__ == "__main__":
    # Example with timed color sets
    cs_definitions = """
    colset INT = int timed;
    colset STRING = string;
    colset PAIR = product(INT, STRING) timed;
    """

    parser = ColorSetParser()
    colorsets = parser.parse_definitions(cs_definitions)

    int_set = colorsets["INT"]
    pair_set = colorsets["PAIR"]

    # Create the CPN structure
    p_int = Place("P_Int", int_set)      # timed place
    p_pair = Place("P_Pair", pair_set)   # timed place
    t = Transition("T", guard="x > 10", variables=["x"])

    cpn = CPN()
    cpn.add_place(p_int)
    cpn.add_place(p_pair)
    # Arc with time delay on output: produced tokens get timestamp = global_clock + 5
    cpn.add_transition(t)
    cpn.add_arc(Arc(p_int, t, "x"))
    cpn.add_arc(Arc(t, p_pair, "(x, 'hello') @+5"))

    # Create a marking
    marking = Marking()
    marking.set_tokens("P_Int", [5, 12])  # both at timestamp 0
    print(cpn)
    print(marking)

    user_code = """
def double(n):
    return n*2
"""
    context = EvaluationContext(user_code=user_code)

    # Check enabling
    print("Is T enabled with x=5?", cpn.is_enabled(t, marking, context, binding={"x": 5}))
    print("Is T enabled with x=12?", cpn.is_enabled(t, marking, context, binding={"x": 12}))

    # Check enabled without providing a binding
    print("Is T enabled without explicit binding?", cpn.is_enabled(t, marking, context))

    # Fire the transition (this should consume the token with value 12)
    cpn.fire_transition(t, marking, context)
    print(marking)

    # The global clock is still 0 because we didn't advance it.
    # The produced token has timestamp = 0 + 5 = 5.
    # If we now advance the global clock:
    cpn.advance_global_clock(marking)
    print("After advancing global clock:", marking.global_clock)
