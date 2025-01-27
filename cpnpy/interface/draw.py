import graphviz
from cpnpy.cpn.cpn_imp import CPN, Marking, Place, Transition, Arc

def cpn_to_graphviz(cpn: CPN, marking: Marking) -> graphviz.Digraph:
    """
    Convert the given CPN and Marking to a Graphviz Digraph for visualization.
    """
    dot = graphviz.Digraph(name="CPN")

    # 1. Add Place nodes
    for place in cpn.places:
        place_id = f"place_{place.name}"
        num_tokens = len(marking.get_multiset(place.name).tokens)
        label = f"{place.name}\\n{repr(place.colorset)}\\nTokens: {num_tokens}"
        dot.node(place_id, label=label, shape="ellipse", style="filled", color="#D3E4CD")

    # 2. Add Transition nodes
    for transition in cpn.transitions:
        transition_id = f"trans_{transition.name}"
        guard_str = transition.guard_expr if transition.guard_expr else "None"
        label = f"{transition.name}\\nguard: {guard_str}\\nvars: {transition.variables}\\ndelay: {transition.transition_delay}"
        dot.node(transition_id, label=label, shape="rectangle", style="filled", color="#FAD4D8")

    # 3. Add Arcs
    for arc in cpn.arcs:
        if isinstance(arc.source, Place):
            src_id = f"place_{arc.source.name}"
        else:
            src_id = f"trans_{arc.source.name}"

        if isinstance(arc.target, Place):
            tgt_id = f"place_{arc.target.name}"
        else:
            tgt_id = f"trans_{arc.target.name}"

        # Arc label is the expression
        dot.edge(src_id, tgt_id, label=arc.expression)

    return dot

def draw_cpn(cpn: CPN, marking: Marking):
    """
    Return a Streamlit-compatible Graphviz chart of the CPN.
    """
    g = cpn_to_graphviz(cpn, marking)
    return g
