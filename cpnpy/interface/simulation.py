import streamlit as st
from cpnpy.cpn.cpn_imp import CPN, Marking, EvaluationContext, Transition


def step_transition(cpn: CPN, transition_name: str, marking: Marking, context: EvaluationContext):
    """
    Attempt to fire the given transition by name. Raises an error if not enabled.
    """
    t = cpn.get_transition_by_name(transition_name)
    if not t:
        st.error(f"Transition '{transition_name}' not found.")
        return

    if cpn.is_enabled(t, marking, context):
        cpn.fire_transition(t, marking, context)
        st.success(f"Fired transition: {transition_name}")
    else:
        st.warning(f"Transition '{transition_name}' is not currently enabled.")

def advance_clock(cpn: CPN, marking: Marking):
    """
    Advance the global clock to the next available timestamp (if any).
    """
    old_time = marking.global_clock
    cpn.advance_global_clock(marking)
    new_time = marking.global_clock
    if new_time == old_time:
        st.info("No future tokens found. Clock remains the same.")
    else:
        st.success(f"Advanced global clock from {old_time} to {new_time}.")


def get_enabled_transitions(cpn: CPN, marking: Marking, context: EvaluationContext):
    """
    Return a list of currently enabled transitions' names.
    """
    enabled = []
    for t in cpn.transitions:
        if cpn.is_enabled(t, marking, context):
            enabled.append(t.name)
    return enabled
