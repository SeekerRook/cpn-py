import networkx as nx
from cpnpy.analysis.reachability import build_reachability_graph
from cpnpy.cpn.cpn_imp import *


def build_scc_graph(RG: nx.DiGraph) -> nx.DiGraph:
    """
    Given a reachability graph RG (as a DiGraph), construct and return
    the SCC graph. Each node in the returned graph represents a strongly
    connected component (SCC) of RG.

    The returned graph is a Directed Acyclic Graph (DAG), known as the condensation
    graph, where each node is an SCC and edges represent connections between SCCs.
    """
    # The condensation function returns a DiGraph representing the SCC graph.
    # Each node of this graph corresponds to an SCC, and it has a node attribute 'members'
    # that is a frozenset of the original nodes in that SCC.
    scc_graph = nx.condensation(RG)
    return scc_graph


# Example usage (assuming you have constructed a reachability graph RG):
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

    # Build the SCC graph
    scc_g = build_scc_graph(RG=RG)

    # Print details of the SCC graph
    print("SCC Graph Nodes:")
    for node, data in scc_g.nodes(data=True):
        print(f"{node}: {data}")

    print("\nSCC Graph Edges:")
    for u, v, edata in scc_g.edges(data=True):
        print(u, "->", v, edata)

    # Now you have a high-level view of the reachability graph structure.
