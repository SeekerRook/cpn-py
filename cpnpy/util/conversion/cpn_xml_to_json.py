import xml.etree.ElementTree as ET
import re
from typing import Dict, Any, List, Optional

def cpn_xml_to_json(xml_path: str) -> Dict[str, Any]:
    """
    Parse a CPN Tools-like XML file and return a dictionary
    conforming to your JSON schema:
      {
        "colorSets": [...],
        "places": [...],
        "transitions": [...],
        "initialMarking": { ... },
        "evaluationContext": null
      }

    The returned dictionary can be converted to JSON if needed.
    """

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # ------------------------------------------------------------------
    # 0. Helper data structures to fill in
    # ------------------------------------------------------------------
    color_sets: List[str] = []
    places: List[Dict[str, str]] = []
    transitions: List[Dict[str, Any]] = []
    initial_marking: Dict[str, Dict[str, Any]] = {}
    # We'll store for each place or transition the "human-readable name" gleaned from <text>
    place_id_to_name: Dict[str, str] = {}
    trans_id_to_name: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # 1. Parse the <globbox> for <color> elements => colorSets
    #    We'll produce strings like "colset X = int;", "colset Y = product(A,B);", etc.
    # ------------------------------------------------------------------
    def parse_color_element(color_elem: ET.Element) -> str:
        """
        Convert a <color> element into a single 'colset <Name> = <Type>;' string.
        This is a simplistic approach. You may need to adapt for enumerations,
        timed sets, etc.
        """
        # <color id="...">
        #   <id>COLOR_NAME</id>
        #   <int/>, <real/>, <string/>, <enum>, <product>, ...
        # Possibly with 'timed="true"' attribute, etc.

        name_elt = color_elem.find("id")  # <id>COLOR_NAME</id>
        if name_elt is not None:
            color_name = name_elt.text.strip()
        else:
            color_name = "UnknownColor"

        # Next, find which child describes the type:
        color_type = "string"  # fallback
        # We do a naive check of children:
        # e.g. <int timed="true"/>, <int/>, <real/>, <string/>, <enum>, <product>
        for child in color_elem:
            tag_lower = child.tag.lower()
            if tag_lower == "int":
                if child.get("timed") == "true":
                    color_type = "int timed"
                else:
                    color_type = "int"
                break
            elif tag_lower == "real":
                color_type = "real"
                break
            elif tag_lower == "string":
                color_type = "string"
                break
            elif tag_lower == "enum":
                # gather enumerated items from <id> sub-elements
                item_texts = []
                for idchild in child.findall("id"):
                    val = idchild.text.strip()
                    # quote them:
                    item_texts.append(f"'{val}'")
                # produce { 'red','green','blue' }
                items_str = ", ".join(item_texts)
                color_type = "{ " + items_str + " }"
                break
            elif tag_lower == "product":
                # gather the <id> children, e.g. <id>COL_A</id>, <id>COL_B</id>
                sub_col_names = []
                for idchild in child.findall("id"):
                    sub_col_names.append(idchild.text.strip())
                inside = ",".join(sub_col_names)
                color_type = f"product({inside})"
                break

        # Return something like "colset COLOR_NAME = int;"
        return f"colset {color_name} = {color_type};"

    # locate the <globbox> if present
    globbox_elem = root.find(".//cpnet/globbox")
    if globbox_elem is not None:
        for color_elem in globbox_elem.findall("color"):
            colset_def = parse_color_element(color_elem)
            color_sets.append(colset_def)

    # ------------------------------------------------------------------
    # 2. Parse <page> for Places, Transitions, Arcs
    #    There might be multiple <page> elements, but let's assume one.
    # ------------------------------------------------------------------
    page_elem = root.find(".//cpnet/page")
    if page_elem is None:
        # No page => no places, no transitions
        pass
    else:
        # ---------------------
        # 2a. Places
        # ---------------------
        for place_elem in page_elem.findall("place"):
            pid = place_elem.get("id", "")
            # The user-friendly name is typically in <text> child
            text_elt = place_elem.find("text")
            place_name = text_elt.text.strip() if text_elt is not None and text_elt.text is not None else pid

            place_id_to_name[pid] = place_name

            # find color set from <type> subelement -> <text>
            color_set_name = "UnknownColorSet"
            type_elem = place_elem.find("type")
            if type_elem is not None:
                # Usually we look for <text> inside <type> or <id> sub
                t_text_elt = type_elem.find("text")
                if t_text_elt is not None and t_text_elt.text:
                    color_set_name = t_text_elt.text.strip()
                else:
                    # might be in <type><id>..., fallback
                    t_id_elt = type_elem.find("id")
                    if t_id_elt is not None and t_id_elt.text:
                        color_set_name = t_id_elt.text.strip()

            # We'll also try to parse initial marking from <initmark> -> <text>
            # E.g. "1`(1,\"ABC\")++1`(2,\"XYZ\")"
            # We'll do a naive parse to produce tokens array (and possibly timestamps).
            initmark_elem = place_elem.find("initmark")
            place_tokens: List[Any] = []
            place_timestamps: List[float] = []
            if initmark_elem is not None:
                im_text_elt = initmark_elem.find("text")
                if im_text_elt is not None and im_text_elt.text:
                    marking_expr = im_text_elt.text.strip()
                    # A simplistic approach: split by "++"
                    # Each part looks like "1`(val)@time" or "1`val"
                    parts = marking_expr.split("++")
                    for part in parts:
                        # remove whitespace
                        part = part.strip()
                        # check for something like: "1`(X,Y)@10" or "1`\"abc\"@2"
                        # We'll do a simple regex to find (value)@time or "value"@time
                        # This is only an example, real data might be more complex.
                        #  pattern could be: ^\d*`(stuff)(@\d+(\.\d+)?)?
                        match = re.match(r"^\d*`(.+?)(?:@([\d.]+))?$", part)
                        if match:
                            token_str = match.group(1)  # e.g. (1,"ABC") or 2
                            time_str = match.group(2)   # e.g. 10 or None
                            if time_str is None:
                                time_val = 0.0
                            else:
                                try:
                                    time_val = float(time_str)
                                except:
                                    time_val = 0.0
                            # parse token_str further if it's a tuple: e.g. (1,"ABC")
                            token_obj = None
                            token_str = token_str.strip()
                            if token_str.startswith("(") and token_str.endswith(")"):
                                # parse inside as a comma list
                                inside = token_str[1:-1].strip()
                                # naive split by comma if no nested parentheses
                                # (Be aware of strings containing commas, etc.)
                                # This is just a demo. Real logic may need a small parser.
                                subvals = split_args_respecting_quotes(inside)
                                parsed_tuple = []
                                for sv in subvals:
                                    sv_clean = sv.strip()
                                    # if it's quoted, treat as string
                                    if sv_clean.startswith('"') or sv_clean.startswith("'"):
                                        parsed_tuple.append(sv_clean.strip('"\''))
                                    else:
                                        # try int or float
                                        try:
                                            parsed_tuple.append(int(sv_clean))
                                        except ValueError:
                                            try:
                                                parsed_tuple.append(float(sv_clean))
                                            except ValueError:
                                                parsed_tuple.append(sv_clean)
                                token_obj = tuple(parsed_tuple)
                            else:
                                # might be a string or int or float
                                if token_str.startswith('"') or token_str.startswith("'"):
                                    token_obj = token_str.strip('"\'')
                                else:
                                    # try number
                                    try:
                                        token_obj = int(token_str)
                                    except ValueError:
                                        try:
                                            token_obj = float(token_str)
                                        except ValueError:
                                            token_obj = token_str
                            place_tokens.append(token_obj)
                            place_timestamps.append(time_val)
                        else:
                            # fallback: entire part is token
                            place_tokens.append(part)
                            place_timestamps.append(0.0)

            # store place and initialMarking
            places.append({
                "name": place_name,
                "colorSet": color_set_name
            })
            if place_tokens:
                # Only store timestamps if there's at least one non-zero
                if any(ts != 0.0 for ts in place_timestamps):
                    initial_marking[place_name] = {
                        "tokens": place_tokens,
                        "timestamps": place_timestamps
                    }
                else:
                    # no real timestamps
                    initial_marking[place_name] = {
                        "tokens": place_tokens
                    }

        # ---------------------
        # 2b. Transitions
        # ---------------------
        for trans_elem in page_elem.findall("trans"):
            tid = trans_elem.get("id", "")
            text_elt = trans_elem.find("text")
            trans_name = text_elt.text.strip() if text_elt is not None and text_elt.text is not None else tid
            trans_id_to_name[tid] = trans_name

        # We'll gather arcs, grouping them by their transition.
        # Then we can fill transitions[i]["inArcs"] / ["outArcs"].
        # We'll store intermediate structure:
        trans_arcs = {tn: {"inArcs": [], "outArcs": []} for tn in trans_id_to_name.values()}

        # parse arcs
        for arc_elem in page_elem.findall("arc"):
            orientation = arc_elem.get("orientation", "")  # "PtoT" or "TtoP" or "BOTHDIR"
            # We want to find placeend and transend
            placeend = arc_elem.find("placeend")
            transend = arc_elem.find("transend")

            if placeend is None or transend is None:
                continue  # malformed arc

            place_idref = placeend.get("idref", "")
            trans_idref = transend.get("idref", "")

            # find the arc annotation text <annot><text>exrpession</text></annot>
            arc_expr = ""
            annot_elt = arc_elem.find("annot")
            if annot_elt is not None:
                text_sub = annot_elt.find("text")
                if text_sub is not None and text_sub.text:
                    arc_expr = text_sub.text.strip()

            # If orientation == "PtoT", place -> transition => an input arc
            if orientation == "PtoT":
                place_name = place_id_to_name.get(place_idref, "UnknownPlace")
                trans_name = trans_id_to_name.get(trans_idref, "UnknownTrans")
                trans_arcs[trans_name]["inArcs"].append({
                    "place": place_name,
                    "expression": arc_expr
                })

            # If orientation == "TtoP", transition -> place => an output arc
            elif orientation == "TtoP":
                trans_name = trans_id_to_name.get(trans_idref, "UnknownTrans")
                place_name = place_id_to_name.get(place_idref, "UnknownPlace")
                trans_arcs[trans_name]["outArcs"].append({
                    "place": place_name,
                    "expression": arc_expr
                })

            # "BOTHDIR" arcs are unusual, but if it appears, we might treat it
            # as two arcs (inArcs + outArcs). This example will just skip or treat as needed.
            # For brevity, we skip "BOTHDIR" handling. Adapt if you need it.

        # Build the final transitions array from trans_arcs
        for tname, arcs_data in trans_arcs.items():
            transitions.append({
                "name": tname,
                # guard / variables / transitionDelay are not shown in the minimal example
                "guard": "",
                "variables": [],
                "transitionDelay": 0,
                "inArcs": arcs_data["inArcs"],
                "outArcs": arcs_data["outArcs"],
            })

    # ------------------------------------------------------------------
    # 3. Build final dictionary. evaluationContext = None
    # ------------------------------------------------------------------
    result = {
        "colorSets": color_sets,
        "places": places,
        "transitions": transitions,
        "initialMarking": initial_marking,
        "evaluationContext": None
    }

    return result

def split_args_respecting_quotes(s: str) -> List[str]:
    """
    Utility to split a string by commas, while ignoring commas inside quotes.
    E.g. '(1,"hello, world",2)' => ["1","\"hello, world\"", "2"]
    This is simplistic (no nested quotes etc.), but enough for basic enumerations.
    """
    # We'll parse char-by-char:
    parts = []
    current = []
    in_quote = None  # track quote type: None / ' / "
    for ch in s:
        if in_quote is None:
            if ch in ("'", '"'):
                # start quote
                in_quote = ch
                current.append(ch)
            elif ch == ',':
                # comma -> split
                parts.append("".join(current))
                current = []
            else:
                current.append(ch)
        else:
            # we are inside a quote
            current.append(ch)
            if ch == in_quote:
                in_quote = None
    # leftover
    if current:
        parts.append("".join(current))
    return [p.strip() for p in parts]
