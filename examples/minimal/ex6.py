from cpnpy.cpn.cpn_imp import *
from cpnpy.analysis.reachability import *


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
