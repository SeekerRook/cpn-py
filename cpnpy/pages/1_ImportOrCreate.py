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

# 3) Import your own modules
from cpnpy.cpn.cpn_imp import CPN, Marking, EvaluationContext
from cpnpy.cpn.colorsets import ColorSetParser
from cpnpy.interface.import_export import import_cpn_ui

def init_session_state():
    """Initialize session state variables if not present."""
    if "cpn" not in st.session_state:
        st.session_state["cpn"] = CPN()
    if "marking" not in st.session_state:
        st.session_state["marking"] = Marking()
    if "colorsets" not in st.session_state:
        st.session_state["colorsets"] = {}
    if "context" not in st.session_state:
        st.session_state["context"] = EvaluationContext()

# Call the init function after everything has been imported
init_session_state()

st.title("Page 1: Import or Create a CPN")

st.markdown(
    """
    **You can either:**
    - Import an existing CPN (JSON) from disk, **or**
    - Create a net from scratch by defining color sets here.
    """
)

# 1) Option A: Import an existing CPN
with st.expander("Import an Existing CPN", expanded=False):
    import_cpn_ui()
    st.info("After a successful import, switch to **Page 2** to edit or simulate the net.")

# 2) Option B: Create from Scratch (Parse Color Sets)
with st.expander("Create from Scratch: Define Color Sets", expanded=False):
    user_color_defs = st.text_area(
        "Enter color set definitions (CPN-Tools-like syntax).",
        height=200,
        placeholder="e.g.\ncolset MyInt = int;\ncolset MyColors = { 'red', 'green' } timed;"
    )

    if st.button("Parse Color Sets"):
        parser = ColorSetParser()
        try:
            parsed = parser.parse_definitions(user_color_defs)
            st.session_state["colorsets"] = parsed
            st.success("Color sets parsed successfully!")
            st.write("Parsed color sets:")
            for name, cs in parsed.items():
                st.write(f"- **{name}**: {repr(cs)}")
        except Exception as e:
            st.error(f"Error parsing color sets: {e}")

st.markdown(
    """
    Once you've **imported** or **parsed** color sets, you can proceed to 
    **Page 2** (Editing & Firing) to build the net (places, transitions, arcs), 
    add tokens, and simulate.
    """
)
