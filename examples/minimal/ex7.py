import json
from cpnpy.cpn.cpn_imp import *   # Assuming this includes the classes CPN, Marking, etc.
from cpnpy.cpn.importer import import_cpn_from_json
from typing import Dict, Any

# Load the JSON specification (the JSON you created previously with places, transitions, etc.)
with open("../../files/minimal_cpns/ex7.json", "r") as f:
    data = json.load(f)

# Import the CPN, its initial marking, and the evaluation context from the JSON
cpn, marking, context = import_cpn_from_json(data)

print("Initial CPN structure:")
print(cpn)
print("\nInitial Marking:")
print(marking)

# Let's pick a transition by name and try to see if it can fire
transition_name = "Send Packet"  # Use one of the transitions defined in the JSON

t = cpn.get_transition_by_name(transition_name)
if t is None:
    raise RuntimeError(f"Transition '{transition_name}' not found in the CPN.")

# Check if the transition is enabled (without explicit binding)
enabled = cpn.is_enabled(t, marking, context)
print(f"\nIs '{transition_name}' enabled without explicit binding?", enabled)

# If it is enabled, fire the transition
if enabled:
    print(f"Firing transition '{transition_name}'...")
    cpn.fire_transition(t, marking, context)

print("\nMarking after attempting to fire transition:")
print(marking)

# Try advancing the global clock (if timed tokens are present, this may move time forward)
cpn.advance_global_clock(marking)
print("\nGlobal clock after advancing:", marking.global_clock)
print("Marking after advancing global clock:")
print(marking)

# If the CPN has another transition that might now be enabled after firing the first one, try that too
another_transition_name = "Transmit Packet"
t2 = cpn.get_transition_by_name(another_transition_name)
if t2:
    enabled_t2 = cpn.is_enabled(t2, marking, context)
    print(f"\nIs '{another_transition_name}' enabled now?", enabled_t2)
    if enabled_t2:
        print(f"Firing transition '{another_transition_name}'...")
        cpn.fire_transition(t2, marking, context)
        print("\nMarking after firing second transition:")
        print(marking)


if True:
    from cpnpy.analysis.analyzer import StateSpaceAnalyzer
    sa = StateSpaceAnalyzer(cpn, marking)
    sa.get_statistics()

if False:
    from cpnpy.visualization.visualizer import CPNGraphViz

    builder = CPNGraphViz()
    builder.apply(cpn, marking)
    builder.view()

