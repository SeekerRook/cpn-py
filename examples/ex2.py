from cpn.cpn import *


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
t = Transition("T", guard="x > 10", variables=["x"])

cpn = CPN()
cpn.add_place(p_int)
cpn.add_place(p_pair)
# Arc with time delay on output: produced tokens get timestamp = global_clock + 5
cpn.add_transition(t)
cpn.add_arc(Arc(p_int, t, "x"))
cpn.add_arc(Arc(t, p_pair, "(x, 'hello') @+5"))

# Create a marking
marking = Marking()
marking.set_tokens("P_Int", [5, 12])  # both at timestamp 0
print(cpn)
print(marking)

user_code = """
def double(n):
    return n*2
"""
context = EvaluationContext(user_code=user_code)

# Check enabling
print("Is T enabled with x=5?", cpn.is_enabled(t, marking, context, binding={"x": 5}))
print("Is T enabled with x=12?", cpn.is_enabled(t, marking, context, binding={"x": 12}))

# Check enabled without providing a binding
print("Is T enabled without explicit binding?", cpn.is_enabled(t, marking, context))

# Fire the transition (this should consume the token with value 12)
cpn.fire_transition(t, marking, context)
print(marking)

# The global clock is still 0 because we didn't advance it.
# The produced token has timestamp = 0 + 5 = 5.
# If we now advance the global clock:
cpn.advance_global_clock(marking)
print("After advancing global clock:", marking.global_clock)
