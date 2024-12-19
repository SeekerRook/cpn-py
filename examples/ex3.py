from cpnpy.cpn.cpn_imp import *
from cpnpy.cpn.importer import *
import json


# Assuming the JSON is in a file "cpn_definition.json"
with open("ex3.json", "r") as f:
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
