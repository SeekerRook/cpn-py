import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Tuple, Union, Optional
import json
from random import randrange
import math

def json_to_cpn_xml(
    json_data: Dict[str, Any],
    coords_data: Dict[str, Any]
) -> str:
    """
    Convert the Petri net definition (json_data) plus coordinate info (coords_data)
    into a CPN Tools (v4.x) XML structure (format="6") as a string.

    The output uses the DTD:
       <!DOCTYPE workspaceElements PUBLIC "-//CPN//DTD CPNXML 1.0//EN" "http://cpntools.org/DTD/6/cpn.dtd">

    and includes:
      - <generator tool="CPN Tools" version="4.0.1" format="6"/>
      - <cpnet> ... </cpnet>
        * <globbox> containing a <block> for color sets/vars
        * <page> with places/transitions/arcs
        * <instances>, <options>, <binders/>, <monitorblock/>, <IndexNode/>

    :param json_data: Dictionary conforming to the given JSON schema.
    :param coords_data: Dictionary containing node coordinates, parsed from an SVG (e.g. from Graphviz).
    :return: A string containing the entire CPN XML with a top-level DOCTYPE line.
    """

    # -------------------------------------------------------------------
    # 0. Helper Functions
    # -------------------------------------------------------------------

    unique_counter = 100  # Simple incremental ID counter, for generating unique IDs.

    def generate_id(prefix: str) -> str:
        """Simple incremental ID generator, to produce unique 'IDxxxx' strings."""
        nonlocal unique_counter
        unique_counter += 1
        return f"ID{prefix}{unique_counter}"

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
                if geom.get("type") == "ellipse":
                    return (geom.get("cx", 0.0), geom.get("cy", 0.0))
        return (0.0, 0.0)

    def parse_cpn_colorset(cs_definition: str) -> (str, ET.Element):
        """
        Very simplistic parser for "colset <Name> = <Type>;" lines.

        Returns: (color_name, color_element), where color_element is the <color> node.

        For CPN Tools 4.x, we'll nest it in a <block>, but the actual <color>:
          <color id='someID'>
            <id>COLORNAME</id>
            <int/>  or <bool/> or <string/> or <unit/> or <real/> or <enum/> or ...
            <layout>colset COLORNAME = <Type>;</layout>
          </color>
        """
        line = cs_definition.strip()
        if not line.lower().startswith("colset "):
            raise ValueError(f"Invalid color set definition: {line}")
        if not line.endswith(";"):
            raise ValueError(f"Invalid color set definition (must end with ';'): {line}")
        # Remove "colset " and trailing ";"
        line = line[len("colset "):]
        line = line[:-1].strip()  # remove final semicolon

        if "=" not in line:
            raise ValueError(f"Invalid color set definition (no '='): {cs_definition}")

        parts = line.split("=", 1)
        color_name = parts[0].strip()
        the_type = parts[1].strip()

        color_id = generate_id("color")
        color_elem = ET.Element("color", {"id": color_id})

        # <id>child</id> with the color set name
        id_child = ET.SubElement(color_elem, "id")
        id_child.text = color_name

        # We'll also attach a <layout> child with the original text:
        layout_child = ET.SubElement(color_elem, "layout")
        layout_child.text = f"colset {color_name} = {the_type};"

        lower_type = the_type.lower()

        # Decide the child node:
        # Examples from CPN Tools standard: <int/>, <bool/>, <string/>, <unit/>, <real/>, <time/>, <intinf/>, ...
        # We'll handle a few typical keywords, else fallback to <string/>.
        if "unit" in lower_type:
            ET.SubElement(color_elem, "unit")
        elif "bool" in lower_type:
            ET.SubElement(color_elem, "bool")
        elif "intinf" in lower_type:
            ET.SubElement(color_elem, "intinf")
        elif "int" in lower_type:
            # If "timed" in there, we might do <int timed='true'/>, but let's keep it minimal:
            # e.g. "colset X = int timed;" => we detect "timed"
            timed_attr = "true" if "timed" in lower_type else None
            if timed_attr:
                sub = ET.SubElement(color_elem, "int")
                sub.set("timed", "true")
            else:
                ET.SubElement(color_elem, "int")
        elif "time" in lower_type:
            ET.SubElement(color_elem, "time")
        elif "real" in lower_type:
            ET.SubElement(color_elem, "real")
        elif "string" in lower_type:
            ET.SubElement(color_elem, "string")
        elif "{" in lower_type and "}" in lower_type:
            # enumerated type, e.g. colset Color = {red, green, blue}
            enum_elem = ET.SubElement(color_elem, "enum")
            inside = the_type[the_type.index("{")+1: the_type.rindex("}")]
            for enumer_val in inside.split(","):
                val = enumer_val.strip().strip("'\"")
                enid = ET.SubElement(enum_elem, "id")
                enid.text = val
        else:
            # Fallback
            ET.SubElement(color_elem, "string")

        return color_name, color_elem

    def gather_all_variables(json_data: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Collects transition variables from the JSON schema. This example lumps them into "INT".
        For a real usage, adapt as needed to read arc expressions or user config.
        Returns { "INT": [var1, var2, ...] } or similar.
        """
        var_map = {}
        for trans in json_data.get("transitions", []):
            for v in trans.get("variables", []):
                var_map.setdefault("INT", []).append(v)
        return var_map

    def create_var_elements(block_elem: ET.Element, var_map: Dict[str, List[str]]):
        """
        Create <var> elements under the given <block> for each colorSet -> [var1, var2, ...].
        We also add a <layout> line for each variable group, e.g. "var x,y : INT;".
        """
        for cs_name, vars_list in var_map.items():
            if not vars_list:
                continue
            var_id = generate_id("var")
            var_elt = ET.SubElement(block_elem, "var", {"id": var_id})

            # color set reference
            t = ET.SubElement(var_elt, "type")
            tid = ET.SubElement(t, "id")
            tid.text = cs_name

            # Add each variable as <id>v</id>
            for v in vars_list:
                v_id = ET.SubElement(var_elt, "id")
                v_id.text = v

            # Provide a layout line
            layout_elt = ET.SubElement(var_elt, "layout")
            layout_elt.text = f"var {','.join(vars_list)} : {cs_name};"

    def build_marking_expression(place_name: str) -> str:
        """
        Build the token marking expression for the place (if any),
        e.g. "1`(x)++2`(y)" etc.
        """
        init_data = json_data.get("initialMarking", {}).get(place_name)
        if not init_data:
            return ""

        tokens = init_data.get("tokens", [])
        timestamps = init_data.get("timestamps", [])

        if len(timestamps) < len(tokens):
            timestamps = [0] * len(tokens)

        parts = []
        for tok, ts in zip(tokens, timestamps):
            if isinstance(tok, (int, float)):
                tok_repr = str(tok)
            elif isinstance(tok, str):
                tok_repr = f"\"{tok}\""
            elif isinstance(tok, (list, tuple)):
                inside = []
                for x in tok:
                    if isinstance(x, (int, float)):
                        inside.append(str(x))
                    else:
                        inside.append(f"\"{x}\"")
                tok_repr = "(" + ",".join(inside) + ")"
            else:
                tok_repr = str(tok)

            if ts != 0:
                full_repr = f"1`{tok_repr}@{ts}"
            else:
                full_repr = f"1`{tok_repr}"
            parts.append(full_repr)

        return "++".join(parts)

    # -------------------------------------------------------------------
    # 1. Prepare the XML structure
    # -------------------------------------------------------------------
    root = ET.Element("workspaceElements")

    # <generator ...>
    gen = ET.SubElement(root, "generator", {
        "tool": "CPN Tools",
        "version": "4.0.1",
        "format": "6"
    })

    cpnet = ET.SubElement(root, "cpnet")

    # -------------------------------------------------------------------
    # 2. GLOBBOX with BLOCKS for color sets, variables, etc.
    # -------------------------------------------------------------------
    globbox = ET.SubElement(cpnet, "globbox")

    # Optionally, create a block for "Standard priorities" or any ML code you want:
    # (comment out if not needed)
    block_standard_priorities = ET.SubElement(globbox, "block", {"id": generate_id("blk")})
    bid1 = ET.SubElement(block_standard_priorities, "id")
    bid1.text = "Standard priorities"

    # Example: define an ML block for P_HIGH, P_NORMAL, etc. (mimicking your example).
    # Remove or adjust these if you don't want them:
    ml_phigh = ET.SubElement(block_standard_priorities, "ml", {"id": generate_id("ml")})
    ml_phigh_layout = ET.SubElement(ml_phigh, "layout")
    ml_phigh_layout.text = "val P_HIGH = 100;"
    ml_phigh.text = "val P_HIGH = 100;"

    ml_pnormal = ET.SubElement(block_standard_priorities, "ml", {"id": generate_id("ml")})
    ml_pnormal_layout = ET.SubElement(ml_pnormal, "layout")
    ml_pnormal_layout.text = "val P_NORMAL = 1000;"
    ml_pnormal.text = "val P_NORMAL = 1000;"

    ml_plow = ET.SubElement(block_standard_priorities, "ml", {"id": generate_id("ml")})
    ml_plow_layout = ET.SubElement(ml_plow, "layout")
    ml_plow_layout.text = "val P_LOW = 10000;"
    ml_plow.text = "val P_LOW = 10000;"

    # Now the main block for standard declarations (color sets, variables, etc.)
    block_decls = ET.SubElement(globbox, "block", {"id": generate_id("blk")})
    block_id_elt = ET.SubElement(block_decls, "id")
    block_id_elt.text = "Standard declarations"

    # 2a. Convert the colorSets strings into <color> elements
    color_name_to_element = {}
    color_sets = json_data.get("colorSets", [])
    for cs_def in color_sets:
        col_name, col_elem = parse_cpn_colorset(cs_def)
        block_decls.append(col_elem)
        color_name_to_element[col_name] = col_elem

    # 2b. Gather variables from transitions -> <var>
    var_map = gather_all_variables(json_data)
    create_var_elements(block_decls, var_map)

    # -------------------------------------------------------------------
    # 3. Create a single <page> to hold places/transitions/arcs
    # -------------------------------------------------------------------
    page_id = generate_id("page")
    page = ET.SubElement(cpnet, "page", {"id": page_id})

    # <pageattr> name
    pageattr = ET.SubElement(page, "pageattr", {"name": "myNet"})

    # We'll track the IDs for places/transitions to link arcs
    place_name_to_id = {}
    transition_name_to_id = {}

    # -------------------------------------------------------------------
    # 4. PLACES
    # -------------------------------------------------------------------
    for place_info in json_data.get("places", []):
        place_name = place_info["name"]
        color_set_name = place_info["colorSet"]

        pid = generate_id("place")
        place_name_to_id[place_name] = pid

        place_elt = ET.SubElement(page, "place", {"id": pid})

        # position from coords
        px, py = find_node_position(place_name)
        ET.SubElement(place_elt, "posattr", {
            "x": f"{px:.6f}",
            "y": f"{py:.6f}"
        })
        # minimal style:
        ET.SubElement(place_elt, "fillattr", {"colour": "White", "pattern": "", "filled": "false"})
        ET.SubElement(place_elt, "lineattr", {"colour": "Black", "thick": "1", "type": "Solid"})
        ET.SubElement(place_elt, "textattr", {"colour": "Black", "bold": "false"})

        # The visible label:
        label_elt = ET.SubElement(place_elt, "text")
        label_elt.text = place_name

        # shape geometry
        ellipse_elt = ET.SubElement(place_elt, "ellipse", {
            "w": "60.000000",
            "h": "40.000000"
        })

        # A minimal "type" child referencing the color set
        type_elt = ET.SubElement(place_elt, "type", {"id": generate_id("type")})
        # Position for the type label
        ET.SubElement(type_elt, "posattr", {
            "x": f"{px + 40.0:.6f}",
            "y": f"{py - 30.0:.6f}"
        })
        # Usually fill/line/text can be blank
        ET.SubElement(type_elt, "fillattr", {"colour": "White", "pattern": "Solid", "filled": "false"})
        ET.SubElement(type_elt, "lineattr", {"colour": "Black", "thick": "0", "type": "Solid"})
        ET.SubElement(type_elt, "textattr", {"colour": "Black", "bold": "false"})

        # The type text
        type_txt = ET.SubElement(type_elt, "text", {"tool":"CPN Tools", "version":"4.0.1"})
        type_txt.text = color_set_name

        # 4a. Build initial marking
        marking_expr = build_marking_expression(place_name)
        if marking_expr:
            # <initmark id='XYZ'>
            initmark_elt = ET.SubElement(place_elt, "initmark", {"id": generate_id("initmark")})
            # position
            ET.SubElement(initmark_elt, "posattr", {
                "x": f"{px:.6f}",
                "y": f"{py + 60.0:.6f}"
            })
            ET.SubElement(initmark_elt, "fillattr", {"colour": "White", "pattern": "Solid", "filled": "false"})
            ET.SubElement(initmark_elt, "lineattr", {"colour": "Black", "thick": "0", "type": "Solid"})
            ET.SubElement(initmark_elt, "textattr", {"colour": "Black", "bold": "false"})
            initmark_text = ET.SubElement(initmark_elt, "text", {"tool":"CPN Tools", "version":"4.0.1"})
            initmark_text.text = marking_expr

            # For the "visual marking" in the net, a <marking> child:
            mark_elt = ET.SubElement(place_elt, "marking", {
                "x": f"{px:.6f}",
                "y": f"{py - 10.0:.6f}",
                "hidden":"false"
            })
            # Provide a <text> with the same expression (or "empty" if none)
            mark_text = ET.SubElement(mark_elt, "text")
            mark_text.text = marking_expr
        else:
            # No tokens => we typically do a <marking> with "empty"
            mark_elt = ET.SubElement(place_elt, "marking", {
                "x": f"{px:.6f}",
                "y": f"{py:.6f}",
                "hidden":"false"
            })
            # The standard text is "empty"
            mark_text = ET.SubElement(mark_elt, "text")
            mark_text.text = "empty"

    # -------------------------------------------------------------------
    # 5. TRANSITIONS
    # -------------------------------------------------------------------
    for trans_info in json_data.get("transitions", []):
        trans_name = trans_info["name"]

        tid = generate_id("trans")
        transition_name_to_id[trans_name] = tid

        trans_elt = ET.SubElement(page, "trans", {
            "id": tid,
            "explicit": "false"
        })

        # position
        tx, ty = find_node_position(trans_name)
        ET.SubElement(trans_elt, "posattr", {
            "x": f"{tx:.6f}",
            "y": f"{ty:.6f}"
        })
        ET.SubElement(trans_elt, "fillattr", {"colour": "White", "pattern": "", "filled": "false"})
        ET.SubElement(trans_elt, "lineattr", {"colour": "Black", "thick": "1", "type": "solid"})
        ET.SubElement(trans_elt, "textattr", {"colour": "Black", "bold": "false"})

        # The visible label
        txt = ET.SubElement(trans_elt, "text")
        txt.text = trans_name

        # shape geometry (a box)
        box_elt = ET.SubElement(trans_elt, "box", {
            "w": "60.000000",
            "h": "40.000000"
        })

        # Provide minimal stubs for other transition-related tags:
        # <binding> for binding arcs. We'll just place it near the transition:
        bind_elt = ET.SubElement(trans_elt, "binding", {
            "x": f"{tx + 7.2:.6f}",
            "y": f"{ty - 3.0:.6f}"
        })

        # Guard/cond expression
        guard_expr = trans_info.get("guard") or ""
        cond_elt = ET.SubElement(trans_elt, "cond", {"id": generate_id("cond")})
        ET.SubElement(cond_elt, "posattr", {
            "x": f"{tx - 10.0:.6f}",
            "y": f"{ty + 19.0:.6f}"
        })
        ET.SubElement(cond_elt, "fillattr", {"colour":"White","pattern":"Solid","filled":"false"})
        ET.SubElement(cond_elt, "lineattr", {"colour":"Black","thick":"0","type":"Solid"})
        ET.SubElement(cond_elt, "textattr", {"colour":"Black","bold":"false"})
        cond_text = ET.SubElement(cond_elt, "text", {"tool":"CPN Tools", "version":"4.0.1"})
        cond_text.text = guard_expr

        # <time> (timed expression or empty)
        time_elt = ET.SubElement(trans_elt, "time", {"id": generate_id("time")})
        ET.SubElement(time_elt, "posattr", {
            "x": f"{tx + 20.0:.6f}",
            "y": f"{ty + 19.0:.6f}"
        })
        ET.SubElement(time_elt, "fillattr", {"colour":"White","pattern":"Solid","filled":"false"})
        ET.SubElement(time_elt, "lineattr", {"colour":"Black","thick":"0","type":"Solid"})
        ET.SubElement(time_elt, "textattr", {"colour":"Black","bold":"false"})
        time_text = ET.SubElement(time_elt, "text", {"tool":"CPN Tools", "version":"4.0.1"})
        time_text.text = ""

        # <code> (ML code or empty)
        code_elt = ET.SubElement(trans_elt, "code", {"id": generate_id("code")})
        ET.SubElement(code_elt, "posattr", {
            "x": f"{tx + 28.0:.6f}",
            "y": f"{ty - 43.0:.6f}"
        })
        ET.SubElement(code_elt, "fillattr", {"colour":"White","pattern":"Solid","filled":"false"})
        ET.SubElement(code_elt, "lineattr", {"colour":"Black","thick":"0","type":"Solid"})
        ET.SubElement(code_elt, "textattr", {"colour":"Black","bold":"false"})
        code_text = ET.SubElement(code_elt, "text", {"tool":"CPN Tools", "version":"4.0.1"})
        code_text.text = ""

        # <priority>
        prio_elt = ET.SubElement(trans_elt, "priority", {"id": generate_id("prio")})
        ET.SubElement(prio_elt, "posattr", {
            "x": f"{tx - 50.0:.6f}",
            "y": f"{ty - 43.0:.6f}"
        })
        ET.SubElement(prio_elt, "fillattr", {"colour":"White","pattern":"Solid","filled":"false"})
        ET.SubElement(prio_elt, "lineattr", {"colour":"Black","thick":"0","type":"Solid"})
        ET.SubElement(prio_elt, "textattr", {"colour":"Black","bold":"false"})
        prio_text = ET.SubElement(prio_elt, "text", {"tool":"CPN Tools", "version":"4.0.1"})
        prio_text.text = ""

    # -------------------------------------------------------------------
    # 6. ARCS (from transitions section in JSON)
    # -------------------------------------------------------------------
    for trans_info in json_data.get("transitions", []):
        trans_name = trans_info["name"]
        trans_id = transition_name_to_id[trans_name]

        # inArcs => orientation="PtoT"
        for arc_info in trans_info.get("inArcs", []):
            place_name = arc_info["place"]
            expr = arc_info["expression"]
            arc_id = generate_id("arc")
            arc_elt = ET.SubElement(page, "arc", {
                "id": arc_id,
                "orientation": "PtoT",
                "order": "1"
            })
            ET.SubElement(arc_elt, "posattr", {"x": "0.000000", "y": "0.000000"})
            ET.SubElement(arc_elt, "fillattr", {"colour": "White", "pattern": "", "filled": "false"})
            ET.SubElement(arc_elt, "lineattr", {"colour": "Black", "thick": "1", "type": "Solid"})
            ET.SubElement(arc_elt, "textattr", {"colour": "Black", "bold": "false"})
            ET.SubElement(arc_elt, "arrowattr", {"headsize": "1.200000", "currentcyckle": "2"})

            # references
            # For P->T arcs, "transend" then "placeend"
            #  (In the example snippet, the order is <transend> then <placeend> if orientation="PtoT" is used.
            #   However, the official doc typically shows placeend then transend.
            #   Either can load in CPN Tools, but let's match the snippet.)
            trans_end = ET.SubElement(arc_elt, "transend", {"idref": trans_id})
            place_end = ET.SubElement(arc_elt, "placeend", {"idref": place_name_to_id[place_name]})

            # <annot> for the arc expression
            annot_id = generate_id("annot")
            annot_elt = ET.SubElement(arc_elt, "annot", {"id": annot_id})
            ET.SubElement(annot_elt, "posattr", {
                "x": "0.000000",
                "y": "0.000000"
            })
            ET.SubElement(annot_elt, "fillattr", {"colour":"White","pattern":"Solid","filled":"false"})
            ET.SubElement(annot_elt, "lineattr", {"colour":"Black","thick":"0","type":"Solid"})
            ET.SubElement(annot_elt, "textattr", {"colour":"Black","bold":"false"})

            annot_text = ET.SubElement(annot_elt, "text", {"tool":"CPN Tools", "version":"4.0.1"})
            annot_text.text = expr

            # An extra empty <text> child is often present in arcs:
            arc_text_child = ET.SubElement(arc_elt, "text")
            arc_text_child.text = ""

        # outArcs => orientation="TtoP"
        for arc_info in trans_info.get("outArcs", []):
            place_name = arc_info["place"]
            expr = arc_info["expression"]
            arc_id = generate_id("arc")
            arc_elt = ET.SubElement(page, "arc", {
                "id": arc_id,
                "orientation": "TtoP",
                "order": "1"
            })
            ET.SubElement(arc_elt, "posattr", {"x": "0.000000", "y": "0.000000"})
            ET.SubElement(arc_elt, "fillattr", {"colour": "White", "pattern": "", "filled": "false"})
            ET.SubElement(arc_elt, "lineattr", {"colour": "Black", "thick": "1", "type": "Solid"})
            ET.SubElement(arc_elt, "textattr", {"colour": "Black", "bold": "false"})
            ET.SubElement(arc_elt, "arrowattr", {"headsize": "1.200000", "currentcyckle": "2"})

            # references
            # For T->P arcs, "transend" then "placeend".
            trans_end = ET.SubElement(arc_elt, "transend", {"idref": trans_id})
            place_end = ET.SubElement(arc_elt, "placeend", {"idref": place_name_to_id[place_name]})

            # <annot> for arc expression
            annot_id = generate_id("annot")
            annot_elt = ET.SubElement(arc_elt, "annot", {"id": annot_id})
            ET.SubElement(annot_elt, "posattr", {
                "x": "0.000000",
                "y": "0.000000"
            })
            ET.SubElement(annot_elt, "fillattr", {"colour":"White","pattern":"Solid","filled":"false"})
            ET.SubElement(annot_elt, "lineattr", {"colour":"Black","thick":"0","type":"Solid"})
            ET.SubElement(annot_elt, "textattr", {"colour":"Black","bold":"false"})

            annot_text = ET.SubElement(annot_elt, "text", {"tool":"CPN Tools", "version":"4.0.1"})
            annot_text.text = expr

            # An extra empty <text> child
            arc_text_child = ET.SubElement(arc_elt, "text")
            arc_text_child.text = ""

    # Add an empty <constraints/> node (CPN Tools often includes it):
    ET.SubElement(page, "constraints")

    # -------------------------------------------------------------------
    # 7. INSTANCES (linking the single page as top-level)
    # -------------------------------------------------------------------
    instances_elt = ET.SubElement(cpnet, "instances")
    # We create an <instance> referencing our page
    ET.SubElement(instances_elt, "instance", {
        "id": f"{page_id}itop",  # e.g. "ID123itop"
        "page": page_id
    })

    # -------------------------------------------------------------------
    # 8. <options> block (replicating your example's defaults)
    # -------------------------------------------------------------------
    options_elt = ET.SubElement(cpnet, "options")

    # Helper to add each <option name='X'><value><boolean>...</boolean></value></option>,
    # or <option name='X' value='text'...>
    def add_option(name, bool_value):
        opt = ET.SubElement(options_elt, "option", {"name": name})
        val = ET.SubElement(opt, "value")
        b = ET.SubElement(val, "boolean")
        b.text = "true" if bool_value else "false"

    # Provide the same set from the example:
    add_option("realtimestamp", False)
    add_option("fair_be", False)
    add_option("global_fairness", False)

    # text-based option:
    opt_dir = ET.SubElement(options_elt, "option", {"name": "outputdirectory"})
    val_dir = ET.SubElement(opt_dir, "value")
    txt_dir = ET.SubElement(val_dir, "text")
    txt_dir.text = "<same as model>"

    # Provide the repeated extension enabling/metrics booleans:
    ext_names = ["extensions.10006.enable","extensions.10001.enable","extensions.10003.enable",
                 "extensions.10005.enable","extensions.10002.enable"]
    for e in ext_names:
        add_option(e, True)

    rep_names = ["repavg", "repciavg","repcount","repfirstval","replastval","repmax","repmin","repssquare","repssqdev","repstddev","repsum","repvariance"]
    # from the snippet: repavg=true, repciavg=true, repcount=false, ...
    # but let's match exactly the snippet:
    rep_values = {
      "repavg": True,
      "repciavg": True,
      "repcount": False,
      "repfirstval": False,
      "replastval": False,
      "repmax": True,
      "repmin": True,
      "repssquare": False,
      "repssqdev": False,
      "repstddev": True,
      "repsum": False,
      "repvariance": False
    }
    for k, v in rep_values.items():
        add_option(k, v)

    # Similarly for the next group: (avg, ciavg, count, firstval, lastval, max, min, ssquare, ssqdev, stddev, sum, variance)
    group_values = {
        "avg": True,
        "ciavg": False,
        "count": True,
        "firstval": False,
        "lastval": False,
        "max": True,
        "min": True,
        "ssquare": False,
        "ssqdev": False,
        "stddev": False,
        "sum": False,
        "variance": False
    }
    for k, v in group_values.items():
        add_option(k, v)

    # Next group: firstupdate, interval, lastupdate, ...
    add_option("firstupdate", False)
    add_option("interval", False)
    add_option("lastupdate", False)

    # Next group: "untimedavg", "untimedciavg", ...
    untimed_values = {
        "untimedavg": True,
        "untimedciavg": False,
        "untimedcount": True,
        "untimedfirstval": False,
        "untimedlastval": False,
        "untimedmax": True,
        "untimedmin": True,
        "untimedssquare": False,
        "untimedssqdev": False,
        "untimedstddev": False,
        "untimedsum": True,
        "untimedvariance": False
    }
    for k, v in untimed_values.items():
        add_option(k, v)

    # -------------------------------------------------------------------
    # 9. <binders/>, <monitorblock>, <IndexNode> stubs
    # -------------------------------------------------------------------
    ET.SubElement(cpnet, "binders")

    monblock = ET.SubElement(cpnet, "monitorblock", {"name":"Monitors"})
    # Example of a monitor as in your snippet (optional). We'll leave it empty or
    # you could replicate an example monitor if you wish:
    # <monitor ...> ... </monitor>

    # The big IndexNode structure from your example (verbatim):
    # (You can simplify or remove this if desired, but it helps CPN Tools re-open properly.)
    index_node = ET.SubElement(cpnet, "IndexNode", {"expanded":"true"})
    # We'll copy the nested structure from your example:
    #  (For brevity, you can remove or reduce; otherwise replicate verbatim.)
    i1 = ET.SubElement(index_node, "IndexNode", {"expanded":"false"})
    i2 = ET.SubElement(index_node, "IndexNode", {"expanded":"false"})
    i3 = ET.SubElement(index_node, "IndexNode", {"expanded":"false"})
    i31 = ET.SubElement(i3, "IndexNode", {"expanded":"false"})
    i311 = ET.SubElement(i31, "IndexNode", {"expanded":"false"})
    i3111 = ET.SubElement(i311, "IndexNode", {"expanded":"false"})
    # ... etc. (matching the full structure from your snippet).
    # For clarity/length, you might replicate all nested <IndexNode expanded='false'>
    # from the example snippet. (Below is a short version.)

    # We'll replicate enough to avoid load issues:
    for _ in range(8):
        subn = ET.SubElement(i311, "IndexNode", {"expanded":"false"})

    i3112 = ET.SubElement(i311, "IndexNode", {"expanded":"false"})
    i312 = ET.SubElement(i31, "IndexNode", {"expanded":"false"})
    # ...
    i4 = ET.SubElement(index_node, "IndexNode", {"expanded":"false"})
    i5 = ET.SubElement(index_node, "IndexNode", {"expanded":"true"})
    i51 = ET.SubElement(i5, "IndexNode", {"expanded":"false"})
    i511 = ET.SubElement(i51, "IndexNode", {"expanded":"true"})
    i512 = ET.SubElement(i51, "IndexNode", {"expanded":"true"})
    i513 = ET.SubElement(i51, "IndexNode", {"expanded":"true"})
    i52 = ET.SubElement(i5, "IndexNode", {"expanded":"true"})
    i521 = ET.SubElement(i52, "IndexNode", {"expanded":"true"})
    # etc. This is purely an example to mimic your snippet's expanded nodes.

    # -------------------------------------------------------------------
    # 10. Produce final string with XML declaration + DOCTYPE
    # -------------------------------------------------------------------
    # Pretty-print (Python 3.9+). For older Pythons, remove ET.indent or replicate manually.
    ET.indent(root, space="  ", level=0)

    xml_str = ET.tostring(root, encoding="utf-8", method="xml").decode("utf-8")
    doctype_line = (
        '<?xml version="1.0" encoding="iso-8859-1"?>\n'
        '<!DOCTYPE workspaceElements PUBLIC "-//CPN//DTD CPNXML 1.0//EN" "http://cpntools.org/DTD/6/cpn.dtd">\n'
    )
    return doctype_line + xml_str


def apply(json_path: str):
    """
    Example function demonstrating how you might integrate:
    1) Parsing a JSON Petri net definition.
    2) Generating an SVG (with cpnpy, Graphviz).
    3) Extracting coordinates from the SVG.
    4) Calling json_to_cpn_xml(...) to produce the final .cpn file content.
    """
    if isinstance(json_path, str):
        with open(json_path, "r") as f:
            data = json.load(f)
    else:
        data = json_path

    # Example usage of cpnpy (comment out if not installed).
    from cpnpy.cpn.importer import import_cpn_from_json
    cpn, marking, context = import_cpn_from_json(data)

    # Create an SVG with Graphviz
    temp_file_name = "temp_" + str(randrange(1, 100000000)).zfill(10)
    from cpnpy.visualization.visualizer import CPNGraphViz
    viz = CPNGraphViz()
    viz.apply(cpn, marking, format="svg")
    viz.save(temp_file_name)

    # Parse coordinates
    from cpnpy.util import svg_parser
    coords = svg_parser.parse_graphviz_svg(temp_file_name + ".svg")

    # Cleanup
    import os
    os.remove(temp_file_name + ".svg")

    # Now produce the final CPN Tools XML
    cpn_xml = json_to_cpn_xml(data, coords)

    return cpn_xml


if __name__ == "__main__":
    # Minimal example JSON:
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
                "variables": ["n", "p"],
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

    cpn_xml_str = apply(sample_json)
    with open("../../../prova.cpn", "w", encoding="utf-8") as f:
        f.write(cpn_xml_str)
