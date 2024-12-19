from cpnpy.cpn.cpn_imp import *


cs_definitions = """
colset INT = int;
colset STRING = string;
colset PAIR = product(INT, STRING);
"""

parser = ColorSetParser()
colorsets = parser.parse_definitions(cs_definitions)

int_set = colorsets["INT"]
pair_set = colorsets["PAIR"]

# Create the CPN structure
p_int = Place("P_Int", int_set)
p_pair = Place("P_Pair", pair_set)
t = Transition("T", guard="x > 10", variables=["x"])

cpn = CPN()
cpn.add_place(p_int)
cpn.add_place(p_pair)
cpn.add_transition(t)
cpn.add_arc(Arc(p_int, t, "x"))
cpn.add_arc(Arc(t, p_pair, "(x, 'hello')"))

# Create a separate marking
marking = Marking()
marking.set_tokens("P_Int", [5, 12])  # Manage marking separately

user_code = """
def double(n):
    return n*2
"""
context = EvaluationContext(user_code=user_code)

print(cpn)
print(marking)

print(cpn.is_enabled(t, marking, context, binding={"x": 5}))
print(cpn.is_enabled(t, marking, context, binding={"x": 12}))

# Check enabled without providing a binding
print("Is T enabled without explicit binding?", cpn.is_enabled(t, marking, context))  # should find binding x=12

# Fire the transition without providing a binding
cpn.fire_transition(t, marking, context)
print(marking)
