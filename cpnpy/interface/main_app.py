import sys
import os
import streamlit as st

# -------------------- Add Project Root to sys.path --------------------
# This ensures Python can locate the cpnpy package when you run:
#   streamlit run cpnpy/interface/main_app.py
# Adjust the relative paths if your directory structure differs.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ----------------------------------------------------------------------

from cpnpy.cpn.colorsets import ColorSetParser
from cpnpy.cpn.cpn_imp import CPN, Marking, EvaluationContext, Place, Transition, Arc

# Import the new import/export UI helpers
from cpnpy.interface.import_export import import_cpn_ui, export_cpn_ui

from cpnpy.interface.draw import draw_cpn
from cpnpy.interface.simulation import (
    step_transition,
    advance_clock,
    get_enabled_transitions,
)


def init_session_state():
    """Initialize Streamlit session state variables if not present."""
    if "color_definitions" not in st.session_state:
        st.session_state["color_definitions"] = ""
    if "colorsets" not in st.session_state:
        st.session_state["colorsets"] = {}
    if "cpn" not in st.session_state:
        st.session_state["cpn"] = CPN()
    if "marking" not in st.session_state:
        st.session_state["marking"] = Marking()
    if "context_code" not in st.session_state:
        st.session_state["context_code"] = ""
    if "context" not in st.session_state:
        st.session_state["context"] = EvaluationContext()


def parse_colorsets():
    """Parse color set definitions from session_state['color_definitions']."""
    parser = ColorSetParser()
    text = st.session_state["color_definitions"]
    try:
        parsed = parser.parse_definitions(text)
        st.session_state["colorsets"] = parsed
        st.success("Color sets parsed successfully!")
    except Exception as e:
        st.error(f"Error parsing color sets: {e}")


def add_place():
    """Add a new place to the CPN based on user input."""
    place_name = st.session_state["new_place_name"]
    cs_name = st.session_state["new_place_colorset"]
    colorsets = st.session_state["colorsets"]

    if not place_name:
        st.warning("Place name cannot be empty.")
        return
    if cs_name not in colorsets:
        st.warning(f"ColorSet '{cs_name}' not found. Please define it first.")
        return

    # Create and add the place
    p = Place(place_name, colorsets[cs_name])
    st.session_state["cpn"].add_place(p)
    st.success(f"Place '{place_name}' added.")


def add_transition():
    """Add a new transition to the CPN based on user input."""
    t_name = st.session_state["new_transition_name"]
    guard_expr = st.session_state["new_transition_guard"]
    vars_str = st.session_state["new_transition_vars"]
    delay = st.session_state["new_transition_delay"]

    if not t_name:
        st.warning("Transition name cannot be empty.")
        return

    variables = [v.strip() for v in vars_str.split(",")] if vars_str.strip() else []
    try:
        delay_val = int(delay)
    except ValueError:
        delay_val = 0

    t = Transition(
        t_name,
        guard_expr.strip() if guard_expr.strip() else None,
        variables,
        delay_val
    )
    st.session_state["cpn"].add_transition(t)
    st.success(f"Transition '{t_name}' added.")


def add_arc():
    """Add a new arc to the CPN based on user input."""
    arc_src_name = st.session_state["new_arc_source"]
    arc_tgt_name = st.session_state["new_arc_target"]
    arc_expr = st.session_state["new_arc_expr"]
    cpn = st.session_state["cpn"]

    if not arc_src_name or not arc_tgt_name:
        st.warning("Source/Target names cannot be empty.")
        return
    if not arc_expr:
        st.warning("Arc expression cannot be empty.")
        return

    # Check if src is place or transition
    src_obj = cpn.get_place_by_name(arc_src_name)
    if not src_obj:
        src_obj = cpn.get_transition_by_name(arc_src_name)
    if not src_obj:
        st.warning(f"Source '{arc_src_name}' not found among places or transitions.")
        return

    # Check if tgt is place or transition
    tgt_obj = cpn.get_place_by_name(arc_tgt_name)
    if not tgt_obj:
        tgt_obj = cpn.get_transition_by_name(arc_tgt_name)
    if not tgt_obj:
        st.warning(f"Target '{arc_tgt_name}' not found among places or transitions.")
        return

    new_arc = Arc(src_obj, tgt_obj, arc_expr)
    cpn.add_arc(new_arc)
    st.success(f"Arc from '{arc_src_name}' to '{arc_tgt_name}' added.")


def add_tokens_to_place():
    """Add tokens to a place in the current marking."""
    place_name = st.session_state["token_place_name"]
    token_val_str = st.session_state["token_value"]

    # Attempt to parse the token value as a Python literal
    try:
        token_value = eval(token_val_str)
    except:
        token_value = token_val_str  # fallback as raw string if eval fails

    cpn = st.session_state["cpn"]
    place = cpn.get_place_by_name(place_name)
    if not place:
        st.warning(f"Place '{place_name}' does not exist.")
        return

    # Validate membership if desired
    if not place.colorset.is_member(token_value):
        st.warning(f"Value {token_value} is not a member of color set {place.colorset}")
        return

    # Timestamp
    timestamp = st.session_state["token_timestamp"]
    try:
        ts_val = int(timestamp)
    except ValueError:
        ts_val = 0

    st.session_state["marking"].add_tokens(place_name, [token_value], timestamp=ts_val)
    st.success(f"Token {token_value} added to place '{place_name}' (t={ts_val}).")


def remove_tokens_from_place():
    """Remove tokens from a place in the current marking."""
    place_name = st.session_state["token_place_name_remove"]
    token_val_str = st.session_state["token_value_remove"]

    cpn = st.session_state["cpn"]
    place = cpn.get_place_by_name(place_name)
    if not place:
        st.warning(f"Place '{place_name}' does not exist.")
        return

    # Attempt to parse the token value
    try:
        token_value = eval(token_val_str)
    except:
        token_value = token_val_str

    marking = st.session_state["marking"]
    try:
        marking.remove_tokens(place_name, [token_value])
        st.success(f"Token {token_value} removed from place '{place_name}'.")
    except Exception as e:
        st.warning(str(e))


def update_context():
    """Update the user's custom context code."""
    user_code = st.session_state["context_code"]
    try:
        # We store the user's original code in a variable so the exporter can detect it
        ctx = EvaluationContext(user_code=user_code)
        # Tag the code as original so exporter can handle it
        ctx.env["__original_user_code__"] = user_code
        st.session_state["context"] = ctx
        st.success("Evaluation context updated successfully!")
    except Exception as e:
        st.error(f"Error updating context: {e}")


def main():
    """
    The main function for running the Streamlit app. It orchestrates:
    1. Session state initialization
    2. Color set parsing
    3. User context code
    4. Net (Place/Transition/Arc) creation
    5. Marking management (adding/removing tokens)
    6. Import/Export of a CPN
    7. Net visualization & simulation controls
    """
    st.title("Colored Petri Net (CPN) Streamlit Interface")

    # 1. Initialize session state
    init_session_state()

    # 2. Color set definitions
    st.sidebar.header("1. Color Sets")
    st.sidebar.text_area(
        "Color Set Definitions (CPN-Tools-like syntax):",
        key="color_definitions",
        height=150,
        placeholder=(
            "e.g.\n"
            "colset MyInt = int;\n"
            "colset MyColors = { 'red', 'green' } timed;"
        )
    )
    if st.sidebar.button("Parse Color Sets"):
        parse_colorsets()

    # Show parsed color sets
    if st.session_state["colorsets"]:
        with st.sidebar.expander("Parsed ColorSets", expanded=False):
            for name, cs in st.session_state["colorsets"].items():
                st.write(f"- **{name}**: {repr(cs)}")

    # 3. User context code
    st.sidebar.header("2. User Context Code (Optional)")
    st.sidebar.text_area(
        "Custom Python code (functions, etc.):",
        key="context_code",
        height=150,
        placeholder="def double(n):\n    return 2*n"
    )
    if st.sidebar.button("Update Context"):
        update_context()

    # 4. Define Net Elements
    st.sidebar.header("3. Define Net Elements")

    # Add Place
    st.sidebar.subheader("Add Place")
    st.sidebar.text_input("Place Name", key="new_place_name", placeholder="e.g. P1")
    st.sidebar.text_input("Colorset Name", key="new_place_colorset", placeholder="e.g. MyInt")
    if st.sidebar.button("Add Place"):
        add_place()

    # Add Transition
    st.sidebar.subheader("Add Transition")
    st.sidebar.text_input("Transition Name", key="new_transition_name", placeholder="e.g. T1")
    st.sidebar.text_input("Guard Expression", key="new_transition_guard", placeholder="e.g. x > 10")
    st.sidebar.text_input("Variables (comma-separated)", key="new_transition_vars", placeholder="e.g. x, y")
    st.sidebar.text_input("Transition Delay (integer)", key="new_transition_delay", value="0")
    if st.sidebar.button("Add Transition"):
        add_transition()

    # Add Arc
    st.sidebar.subheader("Add Arc")
    st.sidebar.text_input("Arc Source (Place or Transition name)", key="new_arc_source", placeholder="P1 or T1")
    st.sidebar.text_input("Arc Target (Place or Transition name)", key="new_arc_target", placeholder="T1 or P2")
    st.sidebar.text_input("Arc Expression", key="new_arc_expr", placeholder="e.g. x, (x,'hello') @+5, etc.")
    if st.sidebar.button("Add Arc"):
        add_arc()

    # 5. Marking Management
    st.sidebar.header("4. Marking Management")

    # Add token
    st.sidebar.subheader("Add Token")
    st.sidebar.text_input("Place name", key="token_place_name", placeholder="e.g. P1")
    st.sidebar.text_input("Token value (Python literal or string)", key="token_value", placeholder="42 or 'red'")
    st.sidebar.text_input("Timestamp (for timed places)", key="token_timestamp", value="0")
    if st.sidebar.button("Add Token"):
        add_tokens_to_place()

    # Remove token
    st.sidebar.subheader("Remove Token")
    st.sidebar.text_input("Place name", key="token_place_name_remove", placeholder="e.g. P1")
    st.sidebar.text_input("Token value (Python literal or string)", key="token_value_remove", placeholder="42 or 'red'")
    if st.sidebar.button("Remove Token"):
        remove_tokens_from_place()

    # 6. Import/Export
    st.sidebar.header("5. Import / Export")
    with st.sidebar.expander("Import CPN"):
        import_cpn_ui()
    with st.sidebar.expander("Export CPN"):
        export_cpn_ui()

    # MAIN DISPLAY AREA

    st.subheader("Current CPN Structure & Marking")
    cpn = st.session_state["cpn"]
    marking = st.session_state["marking"]
    context = st.session_state["context"]

    st.markdown(f"**Global Clock**: {marking.global_clock}")

    # Draw the net
    g = draw_cpn(cpn, marking)
    st.graphviz_chart(g)

    # Show marking details
    with st.expander("Marking Details", expanded=False):
        st.text(repr(marking))

    # Simulation controls
    st.subheader("Simulation Controls")
    enabled_list = get_enabled_transitions(cpn, marking, context)
    if enabled_list:
        st.write("Enabled transitions:", enabled_list)
        chosen_transition = st.selectbox("Choose a transition to fire", enabled_list)
        if st.button("Fire Transition"):
            step_transition(cpn, chosen_transition, marking, context)
    else:
        st.write("No transitions are enabled at the moment.")

    if st.button("Advance Global Clock"):
        advance_clock(cpn, marking)

    st.write("---")
    st.write(
        "**Tip**: If no transitions are enabled, you might need to add tokens or "
        "advance the clock if there are future-timestamped tokens."
    )


if __name__ == "__main__":
    main()
