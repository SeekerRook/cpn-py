import json
import os
from collections import Counter
from typing import Any, Dict, List, Optional, Union

# Import the CPN classes from your existing cpnpy structure
from cpnpy.cpn.cpn_imp import (
    Marking,
    CPN,
    Place,
    Transition,
    Arc,
    Token,
    Multiset,
    EvaluationContext,
)

# Import all color set classes and the parser from colorsets.py
from cpnpy.cpn.colorsets import (
    ColorSet,
    IntegerColorSet,
    RealColorSet,
    StringColorSet,
    BoolColorSet,
    UnitColorSet,
    IntInfColorSet,
    TimeColorSet,
    EnumeratedColorSet,
    ProductColorSet,
    DictionaryColorSet,
    ListColorSet,
    ColorSetParser,
)

# -----------------------------------------------------------------------------------
# Exporter functions
# -----------------------------------------------------------------------------------

def generate_color_set_definitions(cpn: CPN):
    """
    Generate definitions for all distinct color sets used in the CPN, using the types
    from colorsets.py. Returns a tuple (colorset_to_name_map, name_to_definition_map),
    where:
      - colorset_to_name_map: Dict[ColorSet, str] (mapping each ColorSet instance to a generated name)
      - name_to_definition_map: Dict[str, str] (mapping each generated name to a 'colset' definition string)
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

        # Handle each known color set subclass
        if isinstance(cs, IntegerColorSet):
            base_def = f"colset {assigned_name} = int{timed_str};"
        elif isinstance(cs, RealColorSet):
            base_def = f"colset {assigned_name} = real{timed_str};"
        elif isinstance(cs, StringColorSet):
            base_def = f"colset {assigned_name} = string{timed_str};"
        elif isinstance(cs, BoolColorSet):
            base_def = f"colset {assigned_name} = bool{timed_str};"
        elif isinstance(cs, UnitColorSet):
            base_def = f"colset {assigned_name} = unit{timed_str};"
        elif isinstance(cs, IntInfColorSet):
            base_def = f"colset {assigned_name} = intinf{timed_str};"
        elif isinstance(cs, TimeColorSet):
            base_def = f"colset {assigned_name} = time{timed_str};"
        elif isinstance(cs, DictionaryColorSet):
            base_def = f"colset {assigned_name} = dict{timed_str};"
        elif isinstance(cs, EnumeratedColorSet):
            # e.g.: colset X = { 'red', 'green', 'blue' } timed;
            enumerations = ", ".join(f"'{v}'" for v in cs.values)
            base_def = f"colset {assigned_name} = {{ {enumerations} }}{timed_str};"
        elif isinstance(cs, ProductColorSet):
            cs1_name = define_colorset(cs.cs1)
            cs2_name = define_colorset(cs.cs2)
            # e.g. colset X = product(CS0, CS1) timed;
            base_def = f"colset {assigned_name} = product({cs1_name}, {cs2_name}){timed_str};"
        elif isinstance(cs, ListColorSet):
            sub_name = define_colorset(cs.element_cs)
            # e.g. colset X = list CS0 timed;
            base_def = f"colset {assigned_name} = list {sub_name}{timed_str};"
        else:
            raise ValueError(f"Unknown ColorSet type: {cs}")

        name_to_def[assigned_name] = base_def
        return assigned_name

    # Define a colorset name/definition for every place in the CPN
    for p in cpn.places:
        define_colorset(p.colorset)

    return colorset_to_name, name_to_def


def export_cpn_to_json(
    cpn: CPN,
    marking: Marking,
    context: Optional[EvaluationContext],
    output_json_path: str,
    output_py_path: Optional[str] = None
):
    """
    Exports a given CPN, Marking, and optional EvaluationContext to a JSON file.
    Also dumps user-provided Python code (if any) to output_py_path and references
    that file in the resulting JSON for future re-import or usage.
    """
    # Generate color set definitions
    cs_to_name, name_to_def = generate_color_set_definitions(cpn)

    # Places
    places_json = []
    for p in cpn.places:
        places_json.append({
            "name": p.name,
            "colorSet": cs_to_name[p.colorset]
        })

    # Transitions (also gather arcs here)
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

    # Sort color set definitions by their numeric suffix for stable ordering
    sorted_defs = [name_to_def[n] for n in sorted(name_to_def.keys(), key=lambda x: int(x[2:]))]

    # Evaluation Context
    evaluation_context_val = None
    if context is not None:
        user_code = context.env.get('__original_user_code__', None)
        if user_code is not None and user_code.strip():
            # If user_code is actually a file, store the path
            if os.path.isfile(user_code):
                evaluation_context_val = user_code
            else:
                # Otherwise, write inline code to a .py file if specified
                if output_py_path is None:
                    output_py_path = "user_code_exported.py"
                with open(output_py_path, "w") as f:
                    f.write(user_code)
                evaluation_context_val = output_py_path

    # Build the final JSON structure
    final_json = {
        "colorSets": sorted_defs,
        "places": places_json,
        "transitions": transitions_json,
        "initialMarking": initial_marking,
        "evaluationContext": evaluation_context_val
    }

    # Write to JSON file
    with open(output_json_path, "w") as f:
        json.dump(final_json, f, indent=2)

    return final_json


# -----------------------------------------------------------------------------------
# Example Usage (for testing the exporter with the new color sets)
# -----------------------------------------------------------------------------------
if __name__ == "__main__":
    # Use multiline definition for color sets, now parsed via the new parser in colorsets.py
    cs_parser = ColorSetParser()
    cs_defs = cs_parser.parse_definitions("""\
colset INT = int timed;
colset STRING = string;
colset PAIR = product(INT, STRING) timed;
""")
    int_set = cs_defs["INT"]
    pair_set = cs_defs["PAIR"]

    # Create some places and a transition
    p_int = Place("P_Int", int_set)
    p_pair = Place("P_Pair", pair_set)
    t = Transition("T", guard="x > 10", variables=["x"], transition_delay=2)

    # Construct the net
    cpn = CPN()
    cpn.add_place(p_int)
    cpn.add_place(p_pair)
    cpn.add_transition(t)
    cpn.add_arc(Arc(p_int, t, "x"))
    cpn.add_arc(Arc(t, p_pair, "(x, 'hello') @+5"))

    # Marking with some tokens
    marking = Marking()
    marking.set_tokens("P_Int", [5, 12])

    # Create an evaluation context with some user code
    user_code = "def double(n): return n*2"
    context = EvaluationContext(user_code=user_code)

    # Export
    exported = export_cpn_to_json(
        cpn, marking, context,
        output_json_path="cpn_export.json",
        output_py_path="user_code_exported.py"
    )
    print("Exported JSON:")
    print(json.dumps(exported, indent=2))
