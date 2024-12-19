import networkx as nx
from typing import Dict, Any, Tuple, List, Optional, Set
from collections import deque

from cpn.cpn_imp import *


# We assume that the classes CPN, Transition, Place, Marking, EvaluationContext are imported
# from the previously given code snippet.

def marking_to_key(marking: Marking) -> Tuple[int, Tuple[str, Tuple[Tuple[Any, int], ...]]]:
    """
    Convert a Marking object to a hashable key for detecting duplicates in the state space.
    The key includes the global clock and a sorted tuple of places with their tokens.
    Each place is represented by a tuple: (place_name, sorted_tokens_by_value_and_timestamp).
    """
    place_entries = []
    for place_name, ms in sorted(marking._marking.items(), key=lambda x: x[0]):
        # Represent tokens as a sorted tuple of (value, timestamp)
        token_list = sorted((t.value, t.timestamp) for t in ms.tokens)
        place_entries.append((place_name, tuple(token_list)))
    return (marking.global_clock, tuple(place_entries))


def copy_marking(original: Marking) -> Marking:
    """
    Create a deep copy of a marking.
    """
    new_marking = Marking()
    new_marking.global_clock = original.global_clock
    for place_name, ms in original._marking.items():
        # Copy tokens
        tokens_copy = [Token(t.value, t.timestamp) for t in ms.tokens]
        new_marking._marking[place_name] = Multiset(tokens_copy)
    return new_marking


def build_reachability_graph(cpn: CPN, initial_marking: Marking, context: EvaluationContext) -> nx.DiGraph:
    """
    Build the reachability graph of the given CPN starting from initial_marking.
    Return a DiGraph with markings as nodes and transitions as edges.

    The graph's nodes will be keyed by a hashable representation of the marking (to detect duplicates),
    and will have a 'marking' attribute holding the actual Marking object.

    The edges will have attributes:
      - 'transition': the transition name fired
      - 'binding': the binding dict used.

    This procedure uses a BFS-like approach to explore the state space.
    """
    RG = nx.DiGraph()
    visited: Set[Tuple[int, Tuple[str, Tuple[Tuple[Any, int], ...]]]] = set()
    queue = deque()

    init_key = marking_to_key(initial_marking)
    RG.add_node(init_key, marking=copy_marking(initial_marking))
    visited.add(init_key)
    queue.append(init_key)

    while queue:
        current_key = queue.popleft()
        current_marking = RG.nodes[current_key]['marking']

        # Find all enabled transitions and their bindings
        enabled_transitions = []
        for t in cpn.transitions:
            # Find all possible bindings that enable t
            bindings = cpn._find_all_bindings(t, current_marking, context)
            for b in bindings:
                enabled_transitions.append((t, b))

        # If no transitions are enabled, attempt to advance the global clock
        # If advancing the clock enables new transitions, do so. Otherwise, no further expansion is possible.
        if not enabled_transitions:
            old_clock = current_marking.global_clock
            cpn.advance_global_clock(current_marking)
            if current_marking.global_clock > old_clock:
                # Check again if transitions are now enabled
                new_enabled_transitions = []
                for t in cpn.transitions:
                    bindings = cpn._find_all_bindings(t, current_marking, context)
                    for b in bindings:
                        new_enabled_transitions.append((t, b))
                enabled_transitions = new_enabled_transitions

        # For each enabled transition and binding, generate successor marking
        for (trans, binding) in enabled_transitions:
            successor_marking = copy_marking(current_marking)
            # Fire transition
            cpn.fire_transition(trans, successor_marking, context, binding)

            succ_key = marking_to_key(successor_marking)
            if succ_key not in visited:
                RG.add_node(succ_key, marking=successor_marking)
                visited.add(succ_key)
                queue.append(succ_key)

            # Add edge from current to successor
            RG.add_edge(current_key, succ_key, transition=trans.name, binding=binding)

    return RG


# Example usage (place this in a separate test script or main section, not in the package):
if __name__ == "__main__":
    # Example: A simple CPN and initial marking
    cs_definitions = """
    colset INT = int;
    """
    parser = ColorSetParser()
    colorsets = parser.parse_definitions(cs_definitions)

    int_set = colorsets["INT"]
    p1 = Place("P1", int_set)
    p2 = Place("P2", int_set)

    t = Transition("T", guard="x < 5", variables=["x"])
    cpn = CPN()
    cpn.add_place(p1)
    cpn.add_place(p2)
    cpn.add_transition(t)
    cpn.add_arc(Arc(p1, t, "x"))
    cpn.add_arc(Arc(t, p2, "x+1"))

    initial_marking = Marking()
    initial_marking.set_tokens("P1", [0, 1, 2, 3, 4])

    context = EvaluationContext()

    RG = build_reachability_graph(cpn, initial_marking, context)

    # Print the reachability graph
    print("Nodes:")
    for n in RG.nodes(data=True):
        print(n)

    print("\nEdges:")
    for e in RG.edges(data=True):
        print(e)
