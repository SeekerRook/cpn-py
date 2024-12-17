import json
from typing import Dict, Any
from cpn.cpn_imp import *


def import_cpn_from_json(data: Dict[str, Any]) -> (CPN, Marking, EvaluationContext):
    # Parse color sets
    parser = ColorSetParser()
    color_set_defs = data.get("colorSets", [])
    for cs_def in color_set_defs:
        # Each definition must end with a semicolon as per the parser's requirements
        if not cs_def.strip().endswith(";"):
            raise ValueError("Color set definition must end with a semicolon.")
    colorsets = parser.parse_definitions("\n".join(color_set_defs))

    # Create CPN
    cpn = CPN()

    # Create Places
    place_map = {}
    for pdef in data["places"]:
        pname = pdef["name"]
        pcs_name = pdef["colorSet"]
        if pcs_name not in colorsets:
            raise ValueError(f"ColorSet {pcs_name} not defined.")
        place_obj = Place(pname, colorsets[pcs_name])
        cpn.add_place(place_obj)
        place_map[pname] = place_obj

    # Create Transitions and Arcs
    for tdef in data["transitions"]:
        tname = tdef["name"]
        guard = tdef.get("guard", None)
        variables = tdef.get("variables", [])
        transition_delay = tdef.get("transitionDelay", 0)
        t_obj = Transition(tname, guard=guard, variables=variables, transition_delay=transition_delay)
        cpn.add_transition(t_obj)

        # In arcs
        for arc_def in tdef["inArcs"]:
            place_name = arc_def["place"]
            expr = arc_def["expression"]
            if place_name not in place_map:
                raise ValueError(f"Place {place_name} not defined for inArc of transition {tname}.")
            arc = Arc(place_map[place_name], t_obj, expr)
            cpn.add_arc(arc)

        # Out arcs
        for arc_def in tdef["outArcs"]:
            place_name = arc_def["place"]
            expr = arc_def["expression"]
            if place_name not in place_map:
                raise ValueError(f"Place {place_name} not defined for outArc of transition {tname}.")
            arc = Arc(t_obj, place_map[place_name], expr)
            cpn.add_arc(arc)

    # Create initial Marking
    marking = Marking()
    init_marking = data["initialMarking"]
    for pname, mdef in init_marking.items():
        tokens = mdef.get("tokens", [])
        timestamps = mdef.get("timestamps", [0] * len(tokens))
        if len(timestamps) != len(tokens):
            raise ValueError(f"Mismatch between number of tokens and timestamps for place {pname}.")
        marking.set_tokens(pname, tokens, timestamps)

    # Create Evaluation Context
    eval_context_data = data.get("evaluationContext", None)
    if eval_context_data is None:
        context = EvaluationContext(None)
    else:
        # If it's a file path, load the code
        # If it's a string, consider it as inline code
        # Here we assume a file path if not null
        if isinstance(eval_context_data, str):
            with open(eval_context_data, "r") as f:
                user_code = f.read()
            context = EvaluationContext(user_code=user_code)
        else:
            # If it's neither null nor a string, treat it as inline code
            # (User could adapt this logic as needed)
            context = EvaluationContext(str(eval_context_data))

    return cpn, marking, context


# Example usage:
if __name__ == "__main__":
    # Assuming the JSON is in a file "cpn_definition.json"
    with open("../examples/ex3.json", "r") as f:
        data = json.load(f)

    cpn, marking, context = import_cpn_from_json(data)
    print(cpn)
    print(marking)

    t = list(cpn.transitions)[0]

    # Check enabling
    print("Is T enabled with x=5?", cpn.is_enabled(t, marking, context, binding={"x": 5}))
    print("Is T enabled with x=12?", cpn.is_enabled(t, marking, context, binding={"x": 12}))

    # Check enabled without providing a binding
    print("Is T enabled without explicit binding?", cpn.is_enabled(t, marking, context))

    # Fire the transition (this should consume the token with value 12)
    cpn.fire_transition(t, marking, context)
    print(marking)

    # The global clock is still 0.
    # The produced token has timestamp = global_clock + transition_delay (2) + arc_delay (5) = 7.
    cpn.advance_global_clock(marking)
    print("After advancing global clock:", marking.global_clock)
