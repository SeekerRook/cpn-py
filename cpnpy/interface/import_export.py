import streamlit as st
import json

# Use your existing importer/exporter from cpnpy.cpn
from cpnpy.cpn.importer import import_cpn_from_json
from cpnpy.cpn.exporter import export_cpn_to_json
from cpnpy.cpn.colorsets import ColorSetParser


def import_cpn_ui_json():
    """
    Displays a file uploader for importing a CPN from JSON.
    On success, updates:
      - st.session_state["cpn"]
      - st.session_state["marking"]
      - st.session_state["context"]
      - st.session_state["colorsets"] (parsed from the JSON's "colorSets")
      - st.session_state["imported_user_code"] (if the JSON's context had user code)
    We do NOT overwrite any existing text-area widgets in the UI. Instead, we just
    store these imported objects in session_state so the main_app can display them.
    """
    st.subheader("Import CPN from JSON")

    uploaded_file = st.file_uploader("Choose a CPN JSON file", type=["json"])
    if uploaded_file is not None:
        try:
            file_content = uploaded_file.read().decode("utf-8")
            data = json.loads(file_content)

            # 1) Parse colorSets from JSON (if present)
            color_set_defs = data.get("colorSets", [])
            color_definitions_text = "\n".join(color_set_defs)

            parser = ColorSetParser()
            if color_definitions_text.strip():
                parsed_colorsets = parser.parse_definitions(color_definitions_text)
            else:
                parsed_colorsets = {}

            # 2) Import the net, marking, context using your original importer
            cpn, marking, context = import_cpn_from_json(data)

            # 3) Store results in session_state
            st.session_state["cpn"] = cpn
            st.session_state["marking"] = marking
            st.session_state["context"] = context
            st.session_state["colorsets"] = parsed_colorsets

            # If user code was present, store it in a separate key
            imported_code = context.env.get("__original_user_code__", "")
            if imported_code:
                st.session_state["imported_user_code"] = imported_code

            st.success("CPN imported successfully!")
        except Exception as e:
            st.error(f"Failed to import CPN: {e}")


def import_cpn_ui_xml():
    import json
    from cpnpy.util.conversion import cpn_xml_to_json, llm_json_fixing
    from cpnpy.cpn import importer

    st.subheader("Import CPN from XML")

    uploaded_file = st.file_uploader("Choose a CPN file", type=["cpn"])
    if uploaded_file is not None:
        try:
            file_content = uploaded_file.read()
            uploaded_file.close()

            F = open("prova.cpn", "wb")
            F.write(file_content)
            F.close()

            json_dict = cpn_xml_to_json.cpn_xml_to_json("prova.cpn")

            F = open("prova123.json", "w")
            json.dump(json_dict, F, indent=2)
            F.close()

            json_dict = json.loads(llm_json_fixing.fix_json(json_dict))

            F = open("prova456.json", "w")
            json.dump(json_dict, F, indent=2)
            F.close()

            color_set_defs = json_dict.get("colorSets", [])
            color_definitions_text = "\n".join(color_set_defs)

            parser = ColorSetParser()
            if color_definitions_text.strip():
                parsed_colorsets = parser.parse_definitions(color_definitions_text)
            else:
                parsed_colorsets = {}

            cpn, marking, context = importer.import_cpn_from_json(json_dict)

            st.session_state["cpn"] = cpn
            st.session_state["marking"] = marking
            st.session_state["context"] = context
            st.session_state["colorsets"] = parsed_colorsets

            st.success("CPN imported successfully!")
        except Exception as e:
            import traceback
            traceback.print_exc()
            st.error(f"Failed to import CPN: {e}")


def export_cpn_ui():
    """
    Displays a button to export the current CPN+Marking+Context to JSON.
    Offers a download button for the resulting JSON file.
    """
    st.subheader("Export CPN to JSON")

    cpn = st.session_state.get("cpn", None)
    marking = st.session_state.get("marking", None)
    context = st.session_state.get("context", None)

    if not cpn or not marking:
        st.info("No CPN or marking found in session state.")
        return

    # Let the user specify a filename
    filename = st.text_input("Export JSON filename", value="exported_cpn.json")

    if st.button("Export CPN in JSON"):
        try:
            # exporter returns a dict representing the JSON structure
            export_cpn_to_json(
                cpn=cpn,
                marking=marking,
                context=context,
                output_json_path=filename,  # not actually writing to disk except for references
                output_py_path=None         # or "exported_user_code.py", etc.
            )

            exported_str = open(filename, "r").read()

            # Provide a download button
            st.download_button(
                label="Download JSON",
                data=exported_str,
                file_name=filename,
                mime="application/json"
            )
            st.success(f"CPN exported as '{filename}'. Please download it.")
        except Exception as e:
            st.error(f"Error exporting CPN: {e}")

    if st.button("Export CPN in XML (stub)"):
        try:
            # exporter returns a dict representing the JSON structure
            export_cpn_to_json(
                cpn=cpn,
                marking=marking,
                context=context,
                output_json_path=filename,  # not actually writing to disk except for references
                output_py_path=None         # or "exported_user_code.py", etc.
            )

            from cpnpy.util.conversion import json_to_cpn_xml
            cpn_xml = json_to_cpn_xml.apply(filename)

            filename = filename.replace(".json", ".cpn")

            # Provide a download button
            st.download_button(
                label="Download XML",
                data=cpn_xml,
                file_name=filename,
                mime="application/xml"
            )
            st.success(f"CPN exported as '{filename}'. Please download it.")
        except Exception as e:
            import traceback
            traceback.print_exc()

            st.error(f"Error exporting CPN: {e}")
