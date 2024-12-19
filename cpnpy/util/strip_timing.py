import copy


def strip_timed_information(cpn, marking):
    # Deep copy the cpn and marking first
    cpn_copy = copy.deepcopy(cpn)
    marking_copy = copy.deepcopy(marking)

    # 1. Make all places non-timed
    # We assume that each place has a colorset with a 'timed' attribute.
    for p in cpn_copy.places:
        p.colorset.timed = False

    # 2. Reset all transition delays to 0
    for t in cpn_copy.transitions:
        t.transition_delay = 0

    # 3. Remove any arc delays.
    # If an arc expression contains '@+', we strip that part.
    # Example: "x @+5" becomes "x"
    for a in cpn_copy.arcs:
        if '@+' in a.expression:
            a.expression = a.expression.split('@+')[0].strip()

    # 4. Remove all timestamps from tokens in the marking
    for ms in marking_copy._marking.values():
        for tok in ms.tokens:
            tok.timestamp = 0

    # Reset the global clock
    marking_copy.global_clock = 0

    return cpn_copy, marking_copy
