import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Tuple, Union, Optional


def json_to_cpn_xml(
        json_data: Dict[str, Any],
        coords_data: Dict[str, Any]
) -> str:
    """
    Convert the Petri net definition (json_data) plus coordinate info (coords_data)
    into a CPN Tools-like XML structure as a string.

    :param json_data: Dictionary conforming to the given JSON schema.
    :param coords_data: Dictionary conforming to the given coordinate schema
                        (parsed SVG output from Graphviz).
    :return: A string containing the XML (including the CPN Tools DOCTYPE).
    """

    # -------------------------------------------------------------------
    # 0. Helper Functions
    # -------------------------------------------------------------------

    def find_node_position(name: str) -> Tuple[float, float]:
        """
        Given a place/transition name (as used in json_data),
        look up the corresponding node in coords_data["nodes"]
        (where 'title' == name), and return (x, y).

        If not found, returns (0.0, 0.0).
        """
        for node in coords_data.get("nodes", []):
            if node.get("title") == name:
                geom = node.get("geometry", {})
                # If it's an ellipse, we can pick (cx, cy).
                if geom.get("type") == "ellipse":
                    return (geom.get("cx", 0.0), geom.get("cy", 0.0))
                # If it's something else, fallback:
                return (0.0, 0.0)
        return (0.0, 0.0)

    def generate_id(prefix: str) -> str:
        """
        Simple incremental ID generator for example.
        In a real system, you might want more robust unique IDs.
        """
        nonlocal unique_counter
        unique_counter += 1
        return f"id_{prefix}_{unique_counter}"

    def parse_cpn_colorset(cs_definition: str) -> (str, ET.Element):
        """
        Very simplistic parser for "colset <Name> = <Type>;" lines.

        Returns a tuple (color_name, color_element).
        - color_name is the name of the color set.
        - color_element is the <color> ElementTree node.

        NOTE: This is just an example. You may need to adapt to handle
        enumerated sets, products, timed sets, etc., in more detail.
        """
        # Expected basic format: "colset <Name> = something;"
        # Strip "colset" and semicolon:
        line = cs_definition.strip()
        if not line.lower().startswith("colset "):
            raise ValueError(f"Invalid color set definition: {line}")
        # Remove 'colset ' from start:
        line = line[len("colset "):].strip()
        if not line.endswith(";"):
            raise ValueError(f"Invalid color set definition (no ending ';'): {line}")
        line = line[:-1].strip()  # remove trailing semicolon

        # Now line should look like: "<Name> = <Type>"
        if '=' not in line:
            raise ValueError(f"Invalid color set definition (no '='): {cs_definition}")
        parts = line.split('=', 1)
        color_name = parts[0].strip()
        the_type = parts[1].strip()

        # Prepare <color> element
        color_id = generate_id("color")
        color_elem = ET.Element("color", {"id": color_id})

        # <id>child</id> with the color set name
        id_child = ET.SubElement(color_elem, "id")
        id_child.text = color_name

        # Decide the child node based on 'the_type'
        # Basic detection of int, real, string:
        # e.g., "int", "int timed", "real", "string", "product(A,B)", or enumerations {...}
        lower_type = the_type.lower()

        if "int" in lower_type:
            # Could also check if "timed" is present
            if "timed" in lower_type:
                # <int> plus some attribute or subtag for timed
                # The official CPN Tools format for a timed color set can vary, but let's keep it simple:
                int_sub = ET.SubElement(color_elem, "int")
                int_sub.set("timed", "true")
            else:
                # Just an int color
                ET.SubElement(color_elem, "int")

        elif "real" in lower_type:
            ET.SubElement(color_elem, "real")

        elif "string" in lower_type:
            ET.SubElement(color_elem, "string")

        elif "product(" in lower_type:
            # Very simple parse: product(ColA, ColB)
            # We'll create <product><id>ColA</id><id>ColB</id></product>
            prod_elem = ET.SubElement(color_elem, "product")
            # get the inside of product(...)
            inside = the_type.strip()
            inside = inside[len("product("):-1].strip()  # remove "product(" at start and ")" at end
            sub_parts = inside.split(',')
            for sp in sub_parts:
                sub_id = ET.SubElement(prod_elem, "id")
                sub_id.text = sp.strip()

        elif "{" in lower_type and "}" in lower_type:
            # enumerated type, e.g. { 'red','green','blue'}
            # In standard CPN XML, enumerations can be done as <enum><id>val</id>...</enum>
            # We'll do a naive approach:
            enum_elem = ET.SubElement(color_elem, "enum")
            # extract the comma-separated items inside {}
            inside = the_type.strip()
            inside = inside[inside.index('{') + 1: inside.rindex('}')]
            # split by comma
            for enumer_val in inside.split(','):
                val = enumer_val.strip().strip("'\"")
                id_v = ET.SubElement(enum_elem, "id")
                id_v.text = val
        else:
            # Fallback to <string/> if we cannot parse
            ET.SubElement(color_elem, "string")

        return color_name, color_elem

    def gather_all_variables(json_data: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        From all transitions' 'variables', gather them.
        In your schema, each transition can have 'variables': [var1, var2, ...]
        BUT you do not specify which color sets they belong to.

        This function demonstrates grouping them under a single dummy color set "INT"
        or you can adapt to real logic. Returns a dict:

            {
               "INT": ["var1", "var2", ...],
               "DATA": ["p", "str", ...],
               ...
            }

        so we can produce them in <var> elements in the globbox.
        """
        # Example logic: If the user wants to systematically assign them to color sets,
        # you'd parse from arcs or guard expressions, etc.
        # For demonstration, let's just put them all into "INT" (like the example).
        var_map = {}
        for trans in json_data.get("transitions", []):
            for v in trans.get("variables", []):
                # put them in "INT" just as an example
                var_map.setdefault("INT", []).append(v)
        return var_map

    def create_var_elements(parent: ET.Element, var_map: Dict[str, List[str]]):
        """
        Given a dict of colorSetName -> [var1, var2, var3...],
        create <var id="..."> blocks in <globbox>.

        Example:
        <var id="some_id">
          <type>
            <id>INT</id>
          </type>
          <id>n</id>
          <id>k</id>
        </var>
        """
        for cs_name, vars_list in var_map.items():
            if not vars_list:
                continue
            var_elt = ET.SubElement(parent, "var", {"id": generate_id("var")})
            # <type><id>cs_name</id></type>
            t = ET.SubElement(var_elt, "type")
            tid = ET.SubElement(t, "id")
            tid.text = cs_name
            # Then each variable as <id>v</id>
            for v in vars_list:
                v_id = ET.SubElement(var_elt, "id")
                v_id.text = v

    def add_initial_marking(place_elem: ET.Element, place_name: str):
        """
        Add initial marking child (<initmark>) to the <place_elem>,
        based on json_data["initialMarking"][place_name] if present.
        """
        init_data = json_data.get("initialMarking", {}).get(place_name)
        if not init_data:
            return  # No tokens

        tokens = init_data.get("tokens", [])
        timestamps = init_data.get("timestamps", [])
        # If no timestamps, we assume "0" for all
        if len(timestamps) < len(tokens):
            timestamps = [0] * len(tokens)

        # Build a simple text representing the marking, e.g.: 1`(token)
        # or multiple tokens joined by "++"
        # For demonstration, we'll just do something like:
        #  1`(tok_1)++1`(tok_2)...
        # If it's an int/float/string/tuple, we have to convert to text.
        # This is purely an example. In a real scenario, you'd follow your notation rules.
        marking_text_parts = []
        for tok, ts in zip(tokens, timestamps):
            # Turn tok into a string representation:
            if isinstance(tok, (int, float)):
                tok_repr = str(tok)
            elif isinstance(tok, str):
                # wrap quotes?
                tok_repr = f"\"{tok}\""
            elif isinstance(tok, (list, tuple)):
                # e.g. (1,"green")
                inside = []
                for x in tok:
                    if isinstance(x, (int, float)):
                        inside.append(str(x))
                    else:
                        inside.append(f"\"{x}\"")
                tok_repr = "(" + ",".join(inside) + ")"
            else:
                tok_repr = str(tok)

            # If we suspect timed tokens, you might do something like: 1`(val)@ts
            # For demonstration, we just ignore timestamps or show them as '@ts'.
            if ts != 0:
                full_repr = f"1`{tok_repr}@{ts}"
            else:
                full_repr = f"1`{tok_repr}"

            marking_text_parts.append(full_repr)

        marking_expr = "++".join(marking_text_parts)

        initmark_elt = ET.SubElement(place_elem, "initmark", {"id": generate_id("initmark")})
        initmark_pos = ET.SubElement(initmark_elt, "posattr", {
            "x": "0",  # demonstration
            "y": "0"
        })
        # We keep style minimal, but you could do <fillattr>, <lineattr>, <textattr> if you wish.

        text_elt = ET.SubElement(initmark_elt, "text")
        text_elt.text = marking_expr

    # -------------------------------------------------------------------
    # 1. Create Root + DOCTYPE
    #    (ElementTree does not directly let us add a doctype easily;
    #     we'll handle that after building the tree)
    # -------------------------------------------------------------------
    root = ET.Element("workspaceElements")
    # Add <generator tool="CPN Tools" version="0.2.17" format="2"/>
    ET.SubElement(root, "generator", {
        "tool": "CPN Tools",
        "version": "0.2.17",
        "format": "2"
    })

    cpnet = ET.SubElement(root, "cpnet")

    # -------------------------------------------------------------------
    # 2. Build <globbox> with <color> definitions, <var> definitions, etc.
    # -------------------------------------------------------------------
    globbox = ET.SubElement(cpnet, "globbox")

    unique_counter = 100  # We'll store an integer ID counter in an enclosing scope

    # 2a. Convert the colorSets strings into <color> elements
    color_sets = json_data.get("colorSets", [])
    color_name_to_element = {}
    for cs_def in color_sets:
        col_name, col_elem = parse_cpn_colorset(cs_def)
        globbox.append(col_elem)
        color_name_to_element[col_name] = col_elem

    # 2b. Gather variables from transitions, produce <var> blocks
    var_map = gather_all_variables(json_data)
    create_var_elements(globbox, var_map)

    # You could also add extra <ml> or <auxiliary> bits here if desired,
    # e.g., for user-defined ML functions, random seeds, etc.

    # -------------------------------------------------------------------
    # 3. Create a single <page> to hold places/transitions/arcs
    # -------------------------------------------------------------------
    page_id = generate_id("page")
    page = ET.SubElement(cpnet, "page", {"id": page_id})
    # Optional: <pageattr name="Top"/>
    pageattr = ET.SubElement(page, "pageattr", {"name": "Top"})

    # -------------------------------------------------------------------
    # 4. Add PLACES
    # -------------------------------------------------------------------
    place_name_to_id = {}
    for place_info in json_data.get("places", []):
        place_name = place_info["name"]
        color_set_name = place_info["colorSet"]

        place_id = generate_id("place")
        place_name_to_id[place_name] = place_id
        place_elt = ET.SubElement(page, "place", {"id": place_id})

        # position from coords
        px, py = find_node_position(place_name)
        ET.SubElement(place_elt, "posattr", {"x": f"{px}", "y": f"{py}"})
        # minimal style:
        ET.SubElement(place_elt, "fillattr", {"colour": "White", "pattern": "solid", "filled": "false"})
        ET.SubElement(place_elt, "lineattr", {"colour": "Black", "thick": "1", "type": "solid"})
        ET.SubElement(place_elt, "textattr", {"colour": "Black", "bold": "false"})

        # place label:
        text_elt = ET.SubElement(place_elt, "text")
        text_elt.text = place_name

        # shape geometry: we do an <ellipse> for demonstration
        ellipse_elt = ET.SubElement(place_elt, "ellipse", {"w": "30", "h": "20"})

        # Add <type> referencing the color set
        type_elt = ET.SubElement(place_elt, "type", {"id": generate_id("type")})
        # inside <type>, we do <id>colorSetName</id>
        pos_elt = ET.SubElement(type_elt, "posattr", {"x": f"{px}", "y": f"{py}"})
        text_elt2 = ET.SubElement(type_elt, "text")
        text_elt2.text = color_set_name

        # Add initial marking if present
        add_initial_marking(place_elt, place_name)

    # -------------------------------------------------------------------
    # 5. Add TRANSITIONS
    # -------------------------------------------------------------------
    transition_name_to_id = {}
    for trans_info in json_data.get("transitions", []):
        trans_name = trans_info["name"]

        trans_id = generate_id("trans")
        transition_name_to_id[trans_name] = trans_id
        trans_elt = ET.SubElement(page, "trans", {"id": trans_id})

        # position from coords
        tx, ty = find_node_position(trans_name)
        ET.SubElement(trans_elt, "posattr", {"x": f"{tx}", "y": f"{ty}"})
        # minimal style:
        ET.SubElement(trans_elt, "fillattr", {"colour": "White", "pattern": "solid", "filled": "false"})
        ET.SubElement(trans_elt, "lineattr", {"colour": "Black", "thick": "2", "type": "solid"})
        ET.SubElement(trans_elt, "textattr", {"colour": "Black", "bold": "false"})

        # transition label:
        text_elt = ET.SubElement(trans_elt, "text")
        text_elt.text = trans_name

        # shape geometry: box or ellipse
        box_elt = ET.SubElement(trans_elt, "box", {"w": "30", "h": "20"})

        # If there's a guard, you might add a child <cond> or <guard> for the guard expression
        guard_expr = trans_info.get("guard")
        if guard_expr:
            # The real CPN Tools format for a guard is something like <cond>. This is just an example:
            cond_elt = ET.SubElement(trans_elt, "cond")
            cond_elt.text = guard_expr

    # -------------------------------------------------------------------
    # 6. Add ARCS
    #    The JSON schema organizes arcs under transitions: inArcs / outArcs
    # -------------------------------------------------------------------
    for trans_info in json_data.get("transitions", []):
        trans_name = trans_info["name"]
        trans_id = transition_name_to_id[trans_name]

        # inArcs => orientation="PtoT"
        for arc_info in trans_info.get("inArcs", []):
            place_name = arc_info["place"]
            expr = arc_info["expression"]
            # place -> transition
            arc_id = generate_id("arc")
            arc_elt = ET.SubElement(page, "arc", {"id": arc_id, "orientation": "PtoT"})
            # references
            place_end = ET.SubElement(arc_elt, "placeend", {"idref": place_name_to_id[place_name]})
            trans_end = ET.SubElement(arc_elt, "transend", {"idref": trans_id})

            # <annot> for the expression
            annot_id = generate_id("annot")
            annot_elt = ET.SubElement(arc_elt, "annot", {"id": annot_id})
            # minimal position
            ET.SubElement(annot_elt, "posattr", {"x": "0", "y": "0"})
            text_elt = ET.SubElement(annot_elt, "text")
            text_elt.text = expr

        # outArcs => orientation="TtoP"
        for arc_info in trans_info.get("outArcs", []):
            place_name = arc_info["place"]
            expr = arc_info["expression"]
            # transition -> place
            arc_id = generate_id("arc")
            arc_elt = ET.SubElement(page, "arc", {"id": arc_id, "orientation": "TtoP"})
            # references
            trans_end = ET.SubElement(arc_elt, "transend", {"idref": trans_id})
            place_end = ET.SubElement(arc_elt, "placeend", {"idref": place_name_to_id[place_name]})

            # <annot> for expression
            annot_id = generate_id("annot")
            annot_elt = ET.SubElement(arc_elt, "annot", {"id": annot_id})
            ET.SubElement(annot_elt, "posattr", {"x": "0", "y": "0"})
            text_elt = ET.SubElement(annot_elt, "text")
            text_elt.text = expr

    # -------------------------------------------------------------------
    # 7. Produce final string with DOCTYPE
    # -------------------------------------------------------------------
    # Convert ElementTree to string. Then prepend the XML declaration + DOCTYPE.
    # NOTE: If you need pretty-printing, you can use xml.dom.minidom or lxml.
    ET.indent(root, space="  ", level=0)
    xml_str = ET.tostring(root, encoding="utf-8", method="xml").decode("utf-8")

    doctype_line = (
        '<?xml version="1.0" encoding="iso-8859-1"?>\n'
        '<!DOCTYPE workspaceElements PUBLIC "-//CPN//DTD CPNXML 1.0//EN" '
        '"http://www.daimi.au.dk/~cpntools/bin/DTD/2/cpn.dtd">\n'
    )
    return doctype_line + xml_str


if __name__ == "__main__":
    # Minimal example JSON (adjust as needed):
    sample_json = {
        "colorSets": [
            "colset IntSet = int;",
            "colset DataSet = string;"
        ],
        "places": [
            {"name": "P1", "colorSet": "IntSet"},
            {"name": "P2", "colorSet": "DataSet"}
        ],
        "transitions": [
            {
                "name": "T1",
                "variables": ["n", "p"],  # no color set known, defaulting to INT in example
                "inArcs": [
                    {"place": "P1", "expression": "1`n"}
                ],
                "outArcs": [
                    {"place": "P2", "expression": "1`p"}
                ]
            }
        ],
        "initialMarking": {
            "P1": {"tokens": [1, 2]},
            "P2": {"tokens": ["hello"]}
        },
        "evaluationContext": None
    }

    # Minimal coordinate data (must match node titles "P1", "P2", "T1")
    sample_coords = {
        "nodes": [
            {
                "id": "node1",
                "title": "P1",
                "labels": ["P1"],
                "geometry": {"type": "ellipse", "cx": -70.0, "cy": 85.0, "rx": 20.0, "ry": 10.0},
                "text_positions": [(-70.0, 85.0)]
            },
            {
                "id": "node2",
                "title": "P2",
                "labels": ["P2"],
                "geometry": {"type": "ellipse", "cx": 50.0, "cy": 60.0, "rx": 20.0, "ry": 10.0},
                "text_positions": [(50.0, 60.0)]
            },
            {
                "id": "node3",
                "title": "T1",
                "labels": ["T1"],
                "geometry": {"type": "ellipse", "cx": -10.0, "cy": 10.0, "rx": 15.0, "ry": 8.0},
                "text_positions": [(-10.0, 10.0)]
            }
        ],
        "edges": []
    }

    # Generate XML
    cpn_xml = json_to_cpn_xml(sample_json, sample_coords)
    print(cpn_xml)
