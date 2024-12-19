import json
from cpnpy.cpn.cpn_imp import *
from cpnpy.cpn.importer import *


# Load the JSON specification
with open("ex5.json", "r") as f:
    data = json.load(f)

# Import the CPN, its initial marking, and the evaluation context from the JSON
cpn, marking, context = import_cpn_from_json(data)

print("Initial CPN Structure:")
print(cpn)
print("\nInitial Marking:")
print(marking)

# Let's check the transitions and try to fire them if possible.
t1 = cpn.get_transition_by_name("T1")
t2 = cpn.get_transition_by_name("T2")

# Check if T1 is enabled
print("\nIs T1 enabled initially?")
print(cpn.is_enabled(t1, marking, context))

# If T1 is enabled, fire it
if cpn.is_enabled(t1, marking, context):
    print("Firing T1...")
    cpn.fire_transition(t1, marking, context)
    print("Marking after firing T1:")
    print(marking)

# Check if T2 is enabled
print("\nIs T2 enabled initially?")
print(cpn.is_enabled(t2, marking, context))

# If not enabled, let's see if we can make it enabled by advancing time or adding tokens.
# For T2, we need the variable y bound to the token in TimedPlace.
# The initial token in TimedPlace is [10] with timestamp 0.
# Expression is just `y`, so if y=10 and guard is none, it should be enabled.

if cpn.is_enabled(t2, marking, context, binding={"y": 10}):
    print("T2 is enabled with y=10. Firing T2...")
    cpn.fire_transition(t2, marking, context, binding={"y": 10})
    print("Marking after firing T2:")
    print(marking)
else:
    print("T2 is not enabled yet. Consider advancing global clock or changing conditions.")

# Since T2 consumes a timed token and then re-inserts it with a time delay,
# let's advance the global clock and see if that makes a difference.
cpn.advance_global_clock(marking)
print("\nAfter advancing global clock:")
print(marking)
