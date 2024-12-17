from abc import ABC, abstractmethod
from collections import Counter
from typing import Any, Dict, List, Optional, Union

# -----------------------------------------------------------------------------------
# ColorSets
# -----------------------------------------------------------------------------------
class ColorSet(ABC):
    """Abstract base class for representing a color set."""
    @abstractmethod
    def is_member(self, value: Any) -> bool:
        pass

class IntegerColorSet(ColorSet):
    def is_member(self, value: Any) -> bool:
        return isinstance(value, int)

class StringColorSet(ColorSet):
    def is_member(self, value: Any) -> bool:
        return isinstance(value, str)

# -----------------------------------------------------------------------------------
# Token & Multiset
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
        # Check if self is a sub-multiset of other
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
        return f"Multiset({dict(self._counter)})"

# -----------------------------------------------------------------------------------
# Marking
# -----------------------------------------------------------------------------------
class Marking:
    """
    Holds the current distribution of tokens across places.
    """
    def __init__(self):
        self._marking: Dict[str, Multiset] = {}

    def set_tokens(self, place_name: str, tokens: List[Any]):
        # Tokens must already respect the colorset in a well-formed model
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
        return f"Marking({self._marking})"

# -----------------------------------------------------------------------------------
# Place, Transition, Arc
# -----------------------------------------------------------------------------------
class Place:
    def __init__(self, name: str, colorset: ColorSet):
        self.name = name
        self.colorset = colorset

    def __repr__(self):
        return f"Place({self.name}, {self.colorset.__class__.__name__})"

class Transition:
    """
    Guard is a Python expression string that returns True/False.
    Variables used in the guard must be provided in the binding when checking enabling.
    """
    def __init__(self, name: str, guard: Optional[str] = None, variables: Optional[List[str]] = None):
        self.name = name
        self.guard_expr = guard  # Python expression string
        self.variables = variables if variables else []

    def evaluate_guard(self, binding: Dict[str, Any]) -> bool:
        if self.guard_expr is None:
            return True
        return bool(eval(self.guard_expr, {}, binding))

    def __repr__(self):
        return f"Transition({self.name})"

class Arc:
    """
    Arc inscriptions are Python expressions returning either a single value or a list of values.
    They must use the variables that appear in the transitions.
    """
    def __init__(self, source: Union[Place, Transition], target: Union[Place, Transition], expression: str):
        self.source = source
        self.target = target
        self.expression = expression

    def evaluate(self, binding: Dict[str, Any]) -> List[Any]:
        val = eval(self.expression, {}, binding)
        # Normalize to a list
        if isinstance(val, list):
            return val
        else:
            return [val]

    def __repr__(self):
        return f"Arc({self.source}, {self.target})"

# -----------------------------------------------------------------------------------
# CPN
# -----------------------------------------------------------------------------------
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
        # Filter tokens that belong to colorset
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
        # Check guard
        if not t.evaluate_guard(binding):
            return False

        # Check input arcs
        for arc in self.get_input_arcs(t):
            required_values = arc.evaluate(binding)
            # Check if all required_values are in the place marking
            place_marking = self.initial_marking.get_multiset(arc.source.name)
            required_ms = Multiset([Token(v) for v in required_values])
            if not required_ms._counter <= place_marking._counter:
                return False
        return True

    def fire_transition(self, t: Transition, binding: Dict[str, Any]):
        if not self.is_enabled(t, binding):
            raise RuntimeError(f"Transition {t.name} is not enabled under the given binding.")

        # Remove tokens from input places
        for arc in self.get_input_arcs(t):
            required_values = arc.evaluate(binding)
            self.initial_marking.remove_tokens(arc.source.name, required_values)

        # Add tokens to output places
        for arc in self.get_output_arcs(t):
            produced_values = arc.evaluate(binding)
            self.initial_marking.add_tokens(arc.target.name, produced_values)

    def __repr__(self):
        return (f"CPN(places={self.places}, transitions={self.transitions}, arcs={self.arcs}, "
                f"marking={self.initial_marking})")


# -----------------------------------------------------------------------------------
# Example Usage
# -----------------------------------------------------------------------------------
if __name__ == "__main__":
    # Create a simple CPN:
    # Place P with integer tokens
    # Transition T with guard "x > 10"
    # Arc from P to T: expression "x"
    # Arc from T to P: expression "x + 1"

    int_set = IntegerColorSet()
    p = Place("P", int_set)
    t = Transition("T", guard="x > 10", variables=["x"])

    cpn = CPN()
    cpn.add_place(p, initial_tokens=[5, 12])  # P starts with tokens 5 and 12
    cpn.add_transition(t)
    cpn.add_arc(Arc(p, t, "x"))         # input arc: takes a token equal to x
    cpn.add_arc(Arc(t, p, "x + 1"))     # output arc: adds x+1 token to P

    # Test enabling
    binding = {"x": 5}
    print("Is T enabled with x=5?", cpn.is_enabled(t, binding))  # Guard: 5 > 10? False

    binding = {"x": 12}
    print("Is T enabled with x=12?", cpn.is_enabled(t, binding)) # Guard: 12 > 10? True
    cpn.fire_transition(t, binding)
    print("Marking after firing T with x=12:", cpn.initial_marking)
