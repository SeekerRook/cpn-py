import sys
import os
import streamlit as st

# -------------------- Add Project Root to sys.path --------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ----------------------------------------------------------------------

from cpnpy.cpn.colorsets import ColorSetParser
from cpnpy.cpn.cpn_imp import (
    CPN, Marking, EvaluationContext, Place, Transition, Arc
)
from cpnpy.interface.import_export import import_cpn_ui, export_cpn_ui
from cpnpy.interface.draw import draw_cpn
from cpnpy.interface.simulation import (
    step_transition,
    advance_clock,
    get_enabled_transitions,
)

def init_session_state():
    """Initialize Streamlit session state variables, if not present."""
    if "cpn" not in st.session_state:
        st.session_state["cpn"] = CPN()
    if "marking" not in st.session_state:
        st.session_state["marking"] = Marking()
    if "colorsets" not in st.session_state:
        st.session_state["colorsets"] = {}
    if "context" not in st.session_state:
        st.session_state["context"] = EvaluationContext()
    # We'll store user code typed by the user in session_state if they choose to parse it
    if "imported_user_code" not in st.session_state:
        st.session_state["imported_user_code"] = ""


def main():
    """Main Streamlit app function for the Colored Petri Net UI."""
    st.title("Colored Petri Net (CPN) Streamlit Interface")

    # 1) Initialize session state
    init_session_state()

    # --- SIDEBAR LAYOUT ---

    # A) Color Set Input / Parsing
    st.sidebar.header("1. Color Sets")
    # We store the text area in a local variable
    user_color_defs = st.sidebar.text_area(
        "Enter or edit color set definitions here:",
        placeholder="e.g.\ncolset MyInt = int;\ncolset MyColors = { 'red', 'green' } timed;"
    )
    if st.sidebar.button("Parse Color Sets"):
        parser = ColorSetParser()
        try:
            parsed_csets = parser.parse_definitions(user_color_defs)
            st.session_state["colorsets"] = parsed_csets
            st.success("Color sets parsed successfully!")
        except Exception as e:
            st.error(f"Error parsing color sets: {e}")

    # If user has imported color sets, or has newly parsed sets, we show them
    if st.session_state["colorsets"]:
        with st.sidebar.expander("Current Parsed ColorSets", expanded=False):
            for name, cs in st.session_state["colorsets"].items():
                st.write(f" - **{name}**: {repr(cs)}")

    # B) User Context Code
    st.sidebar.header("2. User Context Code (Optional)")
    # Display the user's typed code in a local text area
    user_code_input = st.sidebar.text_area(
        "Python code (functions, etc.):",
        placeholder="def double(n):\n    return 2*n"
    )

    if st.sidebar.button("Set/Update Context with Above Code"):
        try:
            ctx = EvaluationContext(user_code=user_code_input)
            ctx.env["__original_user_code__"] = user_code_input
            st.session_state["context"] = ctx
            st.success("Evaluation context updated with your code!")
        except Exception as e:
            st.error(f"Error updating context: {e}")

    # If there's code from the imported net, show it in a read-only area
    if st.session_state["imported_user_code"]:
        with st.sidebar.expander("Imported User Code", expanded=False):
            st.code(st.session_state["imported_user_code"], language="python")

    # C) Net Elements (Places, Transitions, Arcs)
    st.sidebar.header("3. Define Net Elements")

    st.sidebar.subheader("Add Place")
    place_name = st.sidebar.text_input("Place Name", placeholder="e.g. P1")
    place_cs = st.sidebar.text_input("ColorSet Name", placeholder="e.g. MyInt")
    if st.sidebar.button("Add Place"):
        if not place_name.strip():
            st.warning("Place name cannot be empty.")
        elif place_cs not in st.session_state["colorsets"]:
            st.warning(f"ColorSet '{place_cs}' not found in the current color sets.")
        else:
            p = Place(place_name, st.session_state["colorsets"][place_cs])
            st.session_state["cpn"].add_place(p)
            st.success(f"Place '{place_name}' added.")

    st.sidebar.subheader("Add Transition")
    transition_name = st.sidebar.text_input("Transition Name", placeholder="e.g. T1")
    transition_guard = st.sidebar.text_input("Guard Expression", placeholder="e.g. x > 10")
    transition_vars = st.sidebar.text_input("Variables (comma-separated)", placeholder="e.g. x,y")
    transition_delay = st.sidebar.text_input("Transition Delay (integer)", value="0")
    if st.sidebar.button("Add Transition"):
        if not transition_name.strip():
            st.warning("Transition name cannot be empty.")
        else:
            try:
                delay_val = int(transition_delay)
            except ValueError:
                delay_val = 0
            vars_list = [v.strip() for v in transition_vars.split(",")] if transition_vars.strip() else []
            new_t = Transition(
                transition_name.strip(),
                transition_guard.strip() if transition_guard.strip() else None,
                vars_list,
                delay_val
            )
            st.session_state["cpn"].add_transition(new_t)
            st.success(f"Transition '{transition_name}' added.")

    st.sidebar.subheader("Add Arc")
    arc_src = st.sidebar.text_input("Arc Source (Place or Transition)", placeholder="P1 or T1")
    arc_tgt = st.sidebar.text_input("Arc Target (Place or Transition)", placeholder="T1 or P2")
    arc_expr = st.sidebar.text_input("Arc Expression", placeholder="e.g. x, (x,'hello') @+5")
    if st.sidebar.button("Add Arc"):
        cpn = st.session_state["cpn"]
        if not arc_src.strip() or not arc_tgt.strip():
            st.warning("Source and target cannot be empty.")
        elif not arc_expr.strip():
            st.warning("Arc expression cannot be empty.")
        else:
            # Find source
            src_obj = cpn.get_place_by_name(arc_src)
            if not src_obj:
                src_obj = cpn.get_transition_by_name(arc_src)
            if not src_obj:
                st.warning(f"Source '{arc_src}' not found among places or transitions.")
            else:
                # Find target
                tgt_obj = cpn.get_place_by_name(arc_tgt)
                if not tgt_obj:
                    tgt_obj = cpn.get_transition_by_name(arc_tgt)
                if not tgt_obj:
                    st.warning(f"Target '{arc_tgt}' not found among places or transitions.")
                else:
                    cpn.add_arc(Arc(src_obj, tgt_obj, arc_expr))
                    st.success(f"Arc from '{arc_src}' to '{arc_tgt}' added.")

    # D) Marking Management
    st.sidebar.header("4. Marking Management")
    st.sidebar.subheader("Add Token")
    token_place = st.sidebar.text_input("Place name", placeholder="e.g. P1")
    token_value = st.sidebar.text_input("Token value (Python literal/string)", placeholder="42 or 'red'")
    token_time = st.sidebar.text_input("Timestamp (for timed places)", value="0")
    if st.sidebar.button("Add Token"):
        cpn = st.session_state["cpn"]
        place_obj = cpn.get_place_by_name(token_place)
        if not place_obj:
            st.warning(f"Place '{token_place}' does not exist.")
        else:
            try:
                parsed_val = eval(token_value)
            except:
                parsed_val = token_value
            # Optional membership check
            if not place_obj.colorset.is_member(parsed_val):
                st.warning(f"Value {parsed_val} is not a member of color set {place_obj.colorset}")
            else:
                try:
                    ts_val = int(token_time)
                except ValueError:
                    ts_val = 0
                st.session_state["marking"].add_tokens(token_place, [parsed_val], timestamp=ts_val)
                st.success(f"Token {parsed_val} added to place '{token_place}' (t={ts_val}).")

    st.sidebar.subheader("Remove Token")
    remove_place = st.sidebar.text_input("Place name (remove)", placeholder="e.g. P1")
    remove_val = st.sidebar.text_input("Token value to remove", placeholder="42 or 'red'")
    if st.sidebar.button("Remove Token"):
        cpn = st.session_state["cpn"]
        place_obj = cpn.get_place_by_name(remove_place)
        if not place_obj:
            st.warning(f"Place '{remove_place}' does not exist.")
        else:
            try:
                parsed_val = eval(remove_val)
            except:
                parsed_val = remove_val
            try:
                st.session_state["marking"].remove_tokens(remove_place, [parsed_val])
                st.success(f"Token {parsed_val} removed from place '{remove_place}'.")
            except Exception as ex:
                st.warning(str(ex))

    # E) Import/Export
    st.sidebar.header("5. Import / Export")
    with st.sidebar.expander("Import CPN"):
        import_cpn_ui()
    with st.sidebar.expander("Export CPN"):
        export_cpn_ui()

    # --- MAIN AREA ---

    st.subheader("Current CPN Structure & Marking")

    cpn = st.session_state["cpn"]
    marking = st.session_state["marking"]
    context = st.session_state["context"]

    st.markdown(f"**Global Clock**: {marking.global_clock}")

    # Draw the net
    g = draw_cpn(cpn, marking)
    st.graphviz_chart(g)

    with st.expander("Marking Details", expanded=False):
        st.text(repr(marking))

    # Simulation Controls
    st.subheader("Simulation Controls")
    enabled_list = get_enabled_transitions(cpn, marking, context)
    if enabled_list:
        st.write("Enabled transitions:", enabled_list)
        chosen_transition = st.selectbox("Choose a transition to fire", enabled_list)
        if st.button("Fire Transition"):
            step_transition(cpn, chosen_transition, marking, context)
            # No explicit rerun needed - Streamlit re-runs automatically on button click
    else:
        st.write("No transitions are enabled at the moment.")

    if st.button("Advance Global Clock"):
        advance_clock(cpn, marking)
        # Again, re-run occurs automatically

    st.write("---")
    st.write("**Tip**: If no transitions are enabled, you may need to add tokens "
             "or advance the clock if future-timestamped tokens exist.")


if __name__ == "__main__":
    main()
