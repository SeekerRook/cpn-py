import streamlit as st
import json
import io

from cpnpy.cpn.importer import import_cpn_from_json
from cpnpy.cpn.exporter import export_cpn_to_json
from cpnpy.cpn.cpn_imp import CPN, Marking, EvaluationContext

def import_cpn_ui():
    """
    Renders a file uploader in the Streamlit sidebar (or main page)
    for importing a CPN from JSON. On successful import, updates
    st.session_state['cpn'], st.session_state['marking'], and
    st.session_state['context'].
    """
    st.subheader("Import CPN from JSON")

    uploaded_file = st.file_uploader("Choose a CPN JSON file", type=["json"])
    if uploaded_file is not None:
        try:
            # Read the file as text
            file_content = uploaded_file.read().decode("utf-8")
            data = json.loads(file_content)

            cpn, marking, context = import_cpn_from_json(data)

            # Update session state
            st.session_state["cpn"] = cpn
            st.session_state["marking"] = marking
            st.session_state["context"] = context
            st.success("CPN imported successfully!")
        except Exception as e:
            st.error(f"Failed to import CPN: {e}")


def export_cpn_ui():
    """
    Renders a button that, when clicked, exports the current
    CPN+Marking+Context to JSON. Offers a download button
    for the resulting JSON file.
    """
    st.subheader("Export Current CPN to JSON")

    cpn = st.session_state.get("cpn", None)
    marking = st.session_state.get("marking", None)
    context = st.session_state.get("context", None)

    if not cpn or not marking:
        st.info("No CPN or marking found in the session state.")
        return

    # Let user specify a filename (optional)
    filename = st.text_input("Export JSON filename", value="exported_cpn.json")

    if st.button("Export and Download CPN"):
        try:
            # The exporter returns a dict representing the JSON structure
            exported_json = export_cpn_to_json(
                cpn=cpn,
                marking=marking,
                context=context,
                output_json_path=filename,  # We won't actually write to disk; just for reference
                output_py_path=None         # Or you could specify "exported_user_code.py"
            )
            # Convert to JSON string
            exported_str = json.dumps(exported_json, indent=2)

            # Provide a download button
            st.download_button(
                label="Download CPN JSON",
                data=exported_str,
                file_name=filename,
                mime="application/json"
            )
            st.success(f"CPN exported as '{filename}'.")
        except Exception as e:
            st.error(f"Error exporting CPN: {e}")
