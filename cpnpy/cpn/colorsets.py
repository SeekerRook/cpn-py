from abc import ABC, abstractmethod
from typing import Any, Dict, List


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


class RealColorSet(ColorSet):
    def is_member(self, value: Any) -> bool:
        return isinstance(value, float)

    def __repr__(self):
        timed_str = " timed" if self.timed else ""
        return f"RealColorSet{timed_str}"


class StringColorSet(ColorSet):
    def is_member(self, value: Any) -> bool:
        return isinstance(value, str)

    def __repr__(self):
        timed_str = " timed" if self.timed else ""
        return f"StringColorSet{timed_str}"


class EnumeratedColorSet(ColorSet):
    def __init__(self, values: List[str], timed: bool = False):
        super().__init__(timed=timed)
        self.values = values

    def is_member(self, value: Any) -> bool:
        return value in self.values

    def __repr__(self):
        timed_str = " timed" if self.timed else ""
        values_str = ", ".join(repr(v) for v in self.values)
        return f"EnumeratedColorSet({{{values_str}}}){timed_str}"


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
        # Check for enumerated type: { 'red', 'green', ... }
        if type_str.startswith("{") and type_str.endswith("}"):
            return self._parse_enumerated_type(type_str, timed)

        if type_str == "int":
            return IntegerColorSet(timed=timed)
        if type_str == "real":
            return RealColorSet(timed=timed)
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

    def _parse_enumerated_type(self, type_str: str, timed: bool) -> EnumeratedColorSet:
        # remove outer braces { ... }
        inner = type_str[1:-1].strip()
        if not inner:
            raise ValueError("Enumerated color set cannot be empty.")

        # Enumerations are separated by commas, we assume each value is quoted
        # (e.g., 'red', 'green').
        values = [v.strip() for v in inner.split(",")]
        parsed_values = []
        for val in values:
            if len(val) >= 2 and val.startswith("'") and val.endswith("'"):
                parsed_values.append(val[1:-1])
            else:
                raise ValueError(f"Enumerated values must be quoted strings. Invalid value: {val}")

        return EnumeratedColorSet(parsed_values, timed=timed)

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


if __name__ == "__main__":
    parser = ColorSetParser()

    definitions = """
    colset Colors = { 'red', 'green' } timed;
    colset SimpleColors = { 'blue', 'yellow' };
    colset MyInts = int;
    colset MyReals = real;
    colset MyProduct = product(Colors, MyInts) timed;
    """

    parsed = parser.parse_definitions(definitions)
    for name, cs in parsed.items():
        print(f"{name} = {cs}")

    # Test membership
    print("Test membership:")
    print("Colors.is_member('red'):", parsed['Colors'].is_member('red'))
    print("Colors.is_member('blue'):", parsed['Colors'].is_member('blue'))
    print("SimpleColors.is_member('yellow'):", parsed['SimpleColors'].is_member('yellow'))
    print("MyInts.is_member(42):", parsed['MyInts'].is_member(42))
    print("MyInts.is_member('42'):", parsed['MyInts'].is_member('42'))
    print("MyReals.is_member(3.14):", parsed['MyReals'].is_member(3.14))
    print("MyReals.is_member('3.14'):", parsed['MyReals'].is_member('3.14'))

    # Product test: product(Colors, MyInts)
    print("MyProduct.is_member(('red', 10)):", parsed['MyProduct'].is_member(('red', 10)))
    print("MyProduct.is_member(('red', 'notint')):", parsed['MyProduct'].is_member(('red', 'notint')))
