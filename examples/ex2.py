from cpn.cpn_imp import *
from util import strip_timing

# Example with timed color sets
cs_definitions = """
colset INT = int timed;
colset STRING = string;
colset PAIR = product(INT, STRING) timed;
"""

parser = ColorSetParser()
colorsets = parser.parse_definitions(cs_definitions)

int_set = colorsets["INT"]
pair_set = colorsets["PAIR"]

# Create the CPN structure
p_int = Place("P_Int", int_set)      # timed place
p_pair = Place("P_Pair", pair_set)   # timed place
# Added transition_delay=2 as an example
t = Transition("T", guard="x > 10", variables=["x"], transition_delay=2)

cpn = CPN()
cpn.add_place(p_int)
cpn.add_place(p_pair)
# Arc with time delay on output: produced tokens get timestamp = global_clock + transition_delay + arc_delay
cpn.add_transition(t)
cpn.add_arc(Arc(p_int, t, "x"))
cpn.add_arc(Arc(t, p_pair, "(x, 'hello') @+5"))

# Create a marking
marking = Marking()
marking.set_tokens("P_Int", [5, 12])  # both at timestamp 0

user_code = """
def double(n):
    return n*2
"""
context = EvaluationContext(user_code=user_code)

#cpn, marking = strip_timing.strip_timed_information(cpn, marking); t = cpn.get_transition_by_name("T")
print(cpn)
print(marking)

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
