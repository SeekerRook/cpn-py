import networkx as nx
from typing import Tuple, Set, Callable
from collections import deque
from cpnpy.cpn.cpn_imp import *


def equiv_marking_to_key(marking: Marking) -> Tuple[int, Tuple[Tuple[str, Tuple[Any, ...]], ...]]:
    """
    Convert a Marking object into a canonical representative of its equivalence class.

    This function defines the equivalence relation on markings. In practice, this could be any
    user-defined equivalence relation. The output must be hashable and consistent:
    - If two markings are equivalent, they produce the same canonical key.
    - If two markings are not equivalent, they produce different keys.

    Here, we provide a simple placeholder: it sorts places and tokens as before, which is essentially
    a symmetry that does not change anything. Users should modify this to define a true equivalence.

    Example idea for equivalence:
    - If the tokens differ only by a permutation, consider them equivalent (already handled by sorting).
    - If tokens differ by some isomorphic structure, map them to a canonical form.

    For now, we just reuse the logic of a sorted canonical form.
    Customize this function according to your equivalence requirements.
    """
    place_entries = []
    for place_name, ms in sorted(marking._marking.items(), key=lambda x: x[0]):
        # Represent tokens as a sorted tuple by value and timestamp
        # A true equivalence might disregard timestamps, or group tokens by certain criteria.
        # Adjust as needed.
        token_list = sorted((t.value, t.timestamp) for t in ms.tokens)
        # Example of a more involved equivalence: ignoring timestamps entirely:
        # token_list = sorted(t.value for t in ms.tokens)
        place_entries.append((place_name, tuple(token_list)))

    return (marking.global_clock, tuple(place_entries))


def equiv_binding(binding: Dict[str, Any]) -> Tuple[Tuple[str, Any], ...]:
    """
    Convert a binding dictionary into a canonical representative of its equivalence class.

    As with markings, define your equivalence relation for bindings. For now, we just sort by variable name.
    If two bindings differ in a way that's considered irrelevant under the equivalence relation,
    they should map to the same key.

    Customize this as needed.
    """
    return tuple(sorted(binding.items(), key=lambda x: x[0]))


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


def build_reachability_graph(
        cpn: CPN,
        initial_marking: Marking,
        context: EvaluationContext,
        marking_equiv_func: Callable[[Marking], Any] = equiv_marking_to_key,
        binding_equiv_func: Callable[[Dict[str, Any]], Any] = equiv_binding
) -> nx.DiGraph:
    """
    Build the reachability graph of the given CPN starting from initial_marking.

    This version uses the provided equivalence functions to determine when two states are considered the same.

    Parameters:
      cpn: The Colored Petri Net
      initial_marking: The initial marking of the CPN
      context: The evaluation context for guards and expressions
      marking_equiv_func: A function that returns a canonical representative (key) of a marking's equivalence class.
      binding_equiv_func: A function that returns a canonical representative (key) of a binding's equivalence class.

    Returns:
      A DiGraph with markings as nodes and transitions as edges.
      The nodes are keyed by the canonical representative of the marking (equivalence class).
      The 'marking' attribute of each node holds the actual Marking object.

      Edges have attributes:
        - 'transition': the transition name fired
        - 'binding': the canonical binding key used (equivalence class representative)
    """
    RG = nx.DiGraph()
    visited: Set[Any] = set()  # Set of equivalence class representatives for visited markings
    queue = deque()

    init_key = marking_equiv_func(initial_marking)
    RG.add_node(init_key, marking=copy_marking(initial_marking))
    visited.add(init_key)
    queue.append(init_key)

    while queue:
        current_key = queue.popleft()
        current_marking = RG.nodes[current_key]['marking']

        # Find all enabled transitions and their bindings
        enabled_transitions = []
        for t in cpn.transitions:
            bindings = cpn._find_all_bindings(t, current_marking, context)
            for b in bindings:
                enabled_transitions.append((t, b))

        # If no transitions are enabled, attempt to advance the global clock
        # If advancing the clock enables new transitions, do so. Otherwise, no further expansion.
        if not enabled_transitions:
            old_clock = current_marking.global_clock
            cpn.advance_global_clock(current_marking)
            if current_marking.global_clock > old_clock:
                # Check if transitions are now enabled
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

            succ_key = marking_equiv_func(successor_marking)
            if succ_key not in visited:
                RG.add_node(succ_key, marking=successor_marking)
                visited.add(succ_key)
                queue.append(succ_key)

            # Use binding_equiv_func on the binding if we want equivalence in edges as well
            canonical_binding = binding_equiv_func(binding)
            RG.add_edge(current_key, succ_key, transition=trans.name, binding=canonical_binding)

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

    # Build the reachability graph with equivalence
    RG = build_reachability_graph(cpn, initial_marking, context)

    # Print the reachability graph
    print("Nodes (Equivalence Classes):")
    for n in RG.nodes(data=True):
        print(n)

    print("\nEdges (With Equivalence Classes):")
    for e in RG.edges(data=True):
        print(e)
