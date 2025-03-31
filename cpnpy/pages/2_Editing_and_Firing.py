import sys
import os

# 1) Ensure we can import from cpnpy
current_file = os.path.abspath(__file__)
pages_dir = os.path.dirname(current_file)  # .../cpnpy/pages
cpnpy_dir = os.path.abspath(os.path.join(pages_dir, '..'))  # one level up, .../cpnpy
if cpnpy_dir not in sys.path:
    sys.path.insert(0, cpnpy_dir)
cpnpy_parent = os.path.abspath(os.path.join(cpnpy_dir, '..'))  # parent of cpnpy
if cpnpy_parent not in sys.path:
    sys.path.insert(0, cpnpy_parent)

# 2) Now import streamlit
import streamlit as st

# -------------------------------------------------------
# HELPER FUNCTION: parse user-supplied binding
# -------------------------------------------------------
def parse_binding_to_dict(binding_str: str) -> dict:
    """
    Given a string like "x=42, y='red'", parse it into a dict: {"x": 42, "y": "red"}.
    """
    result = {}
    parts = binding_str.split(',')
    for part in parts:
        part = part.strip()
        if '=' not in part:
            raise ValueError(f"Missing '=' in part '{part}'")
        var_name, val_str = part.split('=', 1)
        var_name = var_name.strip()
        val_str = val_str.strip()
        parsed_val = eval(val_str)  # e.g., eval("42") -> 42, eval("'red'") -> "red"
        result[var_name] = parsed_val
    return result

# 3) Import your Petri net modules
from cpnpy.cpn.cpn_imp import Place, Transition, Arc
from cpnpy.interface.draw import draw_cpn
from cpnpy.interface.simulation import (
    step_transition,
    advance_clock,
    get_enabled_transitions,
)
from cpnpy.interface.import_export import export_cpn_ui

def init_session_state():
    """Ensure session state is ready."""
    if "cpn" not in st.session_state:
        st.session_state["cpn"] = None
    if "marking" not in st.session_state:
        st.session_state["marking"] = None
    if "colorsets" not in st.session_state:
        st.session_state["colorsets"] = {}
    if "context" not in st.session_state:
        st.session_state["context"] = None

init_session_state()

st.title("Page 2: Editing & Firing the CPN")

cpn = st.session_state["cpn"]
marking = st.session_state["marking"]
colorsets = st.session_state["colorsets"]
context = st.session_state["context"]

if not cpn or not marking or not context:
    st.warning("No CPN found. Please go to 'Page 1' to import or create a net first.")
    st.stop()

# Show color sets
if colorsets:
    with st.expander("Current Color Sets", expanded=False):
        for cs_name, cs in colorsets.items():
            st.write(f"- **{cs_name}**: {repr(cs)}")

st.subheader("CPN Editing Tabs")
tabs = st.tabs(["Places", "Transitions", "Arcs", "Marking"])

# ------------------------------------------------------------------------------
# TAB 1: PLACES
# ------------------------------------------------------------------------------
with tabs[0]:
    st.write("### Add Place")
    place_name = st.text_input("Place Name", placeholder="e.g. P1")
    place_cs = st.text_input("ColorSet Name", placeholder="e.g. MyInt")
    if st.button("Add Place"):
        if not place_name.strip():
            st.warning("Place name cannot be empty.")
        elif place_cs not in colorsets:
            st.warning(f"ColorSet '{place_cs}' not found in the current color sets.")
        else:
            new_place = Place(place_name, colorsets[place_cs])
            cpn.add_place(new_place)
            st.success(f"Place '{place_name}' added to the net.")

# ------------------------------------------------------------------------------
# TAB 2: TRANSITIONS
# ------------------------------------------------------------------------------
with tabs[1]:
    st.write("### Add Transition")
    t_name = st.text_input("Transition Name", placeholder="e.g. T1")
    t_guard = st.text_input("Guard Expression", placeholder="e.g. x > 10")
    t_vars = st.text_input("Variables (comma-separated)", placeholder="e.g. x, y")
    t_delay = st.text_input("Transition Delay (integer)", value="0")
    if st.button("Add Transition"):
        if not t_name.strip():
            st.warning("Transition name cannot be empty.")
        else:
            try:
                delay_val = int(t_delay)
            except ValueError:
                delay_val = 0
            variables_list = [v.strip() for v in t_vars.split(",")] if t_vars.strip() else []
            new_t = Transition(
                t_name.strip(),
                guard=t_guard.strip() or None,
                variables=variables_list,
                transition_delay=delay_val
            )
            cpn.add_transition(new_t)
            st.success(f"Transition '{t_name}' added.")

# ------------------------------------------------------------------------------
# TAB 3: ARCS
# ------------------------------------------------------------------------------
with tabs[2]:
    st.write("### Add Arc")
    arc_src = st.text_input("Arc Source (Place or Transition)", placeholder="P1 or T1")
    arc_tgt = st.text_input("Arc Target (Place or Transition)", placeholder="T1 or P2")
    arc_expr = st.text_input("Arc Expression", placeholder="e.g. x, (x,'hello') @+5")
    if st.button("Add Arc"):
        if not arc_src.strip() or not arc_tgt.strip():
            st.warning("Source/Target names cannot be empty.")
        elif not arc_expr.strip():
            st.warning("Arc expression cannot be empty.")
        else:
            src_obj = cpn.get_place_by_name(arc_src)
            if not src_obj:
                src_obj = cpn.get_transition_by_name(arc_src)
            if not src_obj:
                st.warning(f"Source '{arc_src}' not found among places or transitions.")
            else:
                tgt_obj = cpn.get_place_by_name(arc_tgt)
                if not tgt_obj:
                    tgt_obj = cpn.get_transition_by_name(arc_tgt)
                if not tgt_obj:
                    st.warning(f"Target '{arc_tgt}' not found among places or transitions.")
                else:
                    cpn.add_arc(Arc(src_obj, tgt_obj, arc_expr))
                    st.success(f"Arc from '{arc_src}' to '{arc_tgt}' added.")

# ------------------------------------------------------------------------------
# TAB 4: MARKING (Add/Remove Tokens)
# ------------------------------------------------------------------------------
with tabs[3]:
    st.write("### Add/Remove Tokens")
    col1, col2 = st.columns(2)

    with col1:
        st.write("**Add Token**")
        add_token_place = st.text_input("Place name", key="add_token_place", placeholder="e.g. P1")
        add_token_val = st.text_input("Token value (Python literal/string)", key="add_token_val", placeholder="42 or 'red'")
        add_token_ts = st.text_input("Timestamp (for timed places)", key="add_token_ts", value="0")
        if st.button("Add Token", key="btn_add_token"):
            place_obj = cpn.get_place_by_name(add_token_place)
            if not place_obj:
                st.warning(f"Place '{add_token_place}' does not exist.")
            else:
                # Attempt parse
                try:
                    parsed_val = eval(add_token_val)
                except:
                    parsed_val = add_token_val
                # Check membership if desired
                if not place_obj.colorset.is_member(parsed_val):
                    st.warning(f"Value {parsed_val} is not a member of color set {place_obj.colorset}")
                else:
                    try:
                        ts_val = int(add_token_ts)
                    except ValueError:
                        ts_val = 0
                    marking.add_tokens(add_token_place, [parsed_val], timestamp=ts_val)
                    st.success(f"Token {parsed_val} added to place '{add_token_place}' (t={ts_val}).")

    with col2:
        st.write("**Remove Token**")
        rem_place = st.text_input("Place name", key="rem_place", placeholder="e.g. P1")
        rem_val = st.text_input("Token value (Python literal/string)", key="rem_val", placeholder="42 or 'red'")
        if st.button("Remove Token", key="btn_remove_token"):
            place_obj = cpn.get_place_by_name(rem_place)
            if not place_obj:
                st.warning(f"Place '{rem_place}' does not exist.")
            else:
                try:
                    parsed_val = eval(rem_val)
                except:
                    parsed_val = rem_val
                try:
                    marking.remove_tokens(rem_place, [parsed_val])
                    st.success(f"Removed token {parsed_val} from place '{rem_place}'.")
                except Exception as ex:
                    st.warning(str(ex))

# ------------------------------------------------------------------------------
# END TABS: Now show CPN visualization & simulation controls at the bottom
# ------------------------------------------------------------------------------
st.subheader("Current CPN Structure & Marking")
st.markdown(f"**Global Clock**: {marking.global_clock}")

g = draw_cpn(cpn, marking)
st.graphviz_chart(g)

with st.expander("Marking Details", expanded=False):
    st.text(repr(marking))

# Simulation
st.subheader("Simulation Controls")
enabled_list = get_enabled_transitions(cpn, marking, context)
if enabled_list:
    st.write("**Enabled transitions** (with any valid binding):", enabled_list)
    chosen_transition = st.selectbox("Choose a transition to fire", enabled_list, key="fire_transition_select")

    # --- Manual binding support ---
    use_manual_binding = st.checkbox("Use a Manual Binding?", value=False)
    binding_str = ""
    if use_manual_binding:
        # Let user specify "x=42, y='red'" etc.
        binding_str = st.text_input(
            label="Binding (e.g. x=42, y='red')",
            placeholder="x=42, y='red'"
        )

    if st.button("Fire Transition"):
        binding = None
        if use_manual_binding and binding_str.strip():
            try:
                binding = parse_binding_to_dict(binding_str)
            except Exception as e:
                st.warning(f"Could not parse binding: {e}")
                binding = None

        if binding:
            # Fire transition with user-specified binding
            t_obj = cpn.get_transition_by_name(chosen_transition)
            if not t_obj:
                st.error("Transition not found (unexpected).")
            else:
                # Check if enabled with that binding
                if cpn.is_enabled(t_obj, marking, context, binding=binding):
                    cpn.fire_transition(t_obj, marking, context, binding=binding)
                    st.success(f"Fired transition '{chosen_transition}' with binding {binding}.")
                else:
                    st.warning(f"Transition '{chosen_transition}' not enabled with binding {binding}.")
        else:
            # Fallback: no manual binding
            from cpnpy.interface.simulation import step_transition
            step_transition(cpn, chosen_transition, marking, context)
else:
    st.write("No transitions are enabled at the moment.")

colA, colB = st.columns(2)

with colA:
    if st.button("Advance Global Clock"):
        advance_clock(cpn, marking)

with colB:
    if st.button("Update Visualized Information"):
        st.info("Visualization and Marking updated!")

# Export
st.subheader("Export CPN")
export_cpn_ui()

st.write("---")
st.write("**Tip**: Return to **Page 1** to import a different net or define new color sets.")
