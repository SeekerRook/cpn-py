import xml.etree.ElementTree as ET
import re
from typing import Dict, Any, List, Optional, Union

def cpn_xml_to_json(xml_path: str) -> Dict[str, Any]:
    """
    Parse a CPN Tools-like XML file and return a dictionary
    conforming to your JSON schema:
      {
        "colorSets": [...],
        "places": [...],
        "transitions": [...],
        "initialMarking": { ... },
        "evaluationContext": null or "some string with ML code"
      }

    This version handles:
      - A broader range of color set constructs,
      - Transition guard extraction from <condition><annot><text>,
      - Transition variables from <code><ml>,
      - Capturing ML code from <globbox><ml> into evaluationContext.
    """

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # ------------------------------------------------------------------
    # Storage structures
    # ------------------------------------------------------------------
    color_sets: List[str] = []
    places: List[Dict[str, str]] = []
    transitions: List[Dict[str, Any]] = []
    initial_marking: Dict[str, Dict[str, Any]] = {}

    # Maps from CPN <place id="..."> or <trans id="..."> to the displayed name in <text>
    place_id_to_name: Dict[str, str] = {}
    trans_id_to_name: Dict[str, str] = {}

    # Will hold code from <globbox><ml> as a single string, or None if none is found
    evaluation_context: Optional[str] = None

    # ------------------------------------------------------------------
    # 1. Parse color sets in <globbox> -> <color>
    #    Also gather any <ml> content for the evaluationContext.
    # ------------------------------------------------------------------
    globbox_elem = root.find(".//cpnet/globbox")

    def parse_color_element(color_elem: ET.Element) -> str:
        """
        Convert a <color> element into a 'colset <Name> = <Type>;' string.
        If <layout> is present, we use that text directly (like "colset MYCOL = int;").
        Otherwise, we inspect child tags to guess the color definition.
        """
        # 1) Extract color name from <id> child
        name_elt = color_elem.find("id")
        if name_elt is not None and name_elt.text:
            color_name = name_elt.text.strip()
        else:
            color_name = "UnknownColor"

        # 2) If there's a <layout> child, use that text directly.
        #    Typically <layout> is something like: "colset UNIT_TIMED = UNIT timed;"
        layout_elt = color_elem.find("layout")
        if layout_elt is not None and layout_elt.text:
            # Just return that line as is (trim any whitespace).
            layout_text = layout_elt.text.strip()
            return layout_text

        # 3) Otherwise, build from known child tags:
        color_type = ""
        timed_flag = False
        alias_target = None
        list_target = None

        for child in color_elem:
            tag_lower = child.tag.lower()
            if tag_lower == "int":
                color_type = "int"
            elif tag_lower == "real":
                color_type = "real"
            elif tag_lower == "string":
                color_type = "string"
            elif tag_lower == "bool":
                color_type = "bool"
            elif tag_lower == "unit":
                color_type = "unit"
            elif tag_lower == "intinf":
                color_type = "intinf"
            elif tag_lower == "time":
                color_type = "time"
            elif tag_lower == "timed":
                timed_flag = True
            elif tag_lower == "enum":
                # gather enumerated items from <id> sub-elements
                item_texts = []
                for idchild in child.findall("id"):
                    val = idchild.text.strip()
                    item_texts.append(val)
                joined = ", ".join(f"'{x}'" for x in item_texts)
                color_type = f"{{ {joined} }}"
            elif tag_lower == "product":
                sub_col_names = [idchild.text.strip() for idchild in child.findall("id")]
                color_type = f"product({','.join(sub_col_names)})"
            elif tag_lower == "alias":
                a_id = child.find("id")
                if a_id is not None and a_id.text:
                    alias_target = a_id.text.strip()
            elif tag_lower == "list":
                l_id = child.find("id")
                if l_id is not None and l_id.text:
                    list_target = l_id.text.strip()
            # ... handle other tags as needed

        # Now assemble from alias/list/timed
        if alias_target and list_target:
            # This combination is odd, but let's ignore or handle if needed
            pass
        elif alias_target:
            # "colset X = <alias_target> timed;" if timed_flag else just <alias_target>
            base_str = alias_target
            if timed_flag:
                color_type = f"{base_str} timed"
            else:
                color_type = base_str
        elif list_target:
            color_type = f"list {list_target}"
        else:
            if not color_type:
                color_type = "string"

        if timed_flag and not alias_target and not color_type.endswith("timed"):
            if color_type and "timed" not in color_type:
                color_type += " timed"

        return f"colset {color_name} = {color_type};"

    if globbox_elem is not None:
        # Parse <color> definitions
        for color_elem in globbox_elem.findall(".//color"):
            colset_def = parse_color_element(color_elem)
            if colset_def.strip():
                color_sets.append(colset_def)

        # Parse <ml> content (if any) to store in evaluationContext
        # We'll concatenate all <ml> blocks into one multi-line string.
        ml_blocks = globbox_elem.findall("ml")
        if ml_blocks:
            lines = []
            for mlb in ml_blocks:
                if mlb.text and mlb.text.strip():
                    lines.append(mlb.text.strip())
            if lines:
                evaluation_context = "\n\n".join(lines)

    # ------------------------------------------------------------------
    # 2. Parse <page> for Places, Transitions, Arcs
    # ------------------------------------------------------------------
    page_elem = root.find(".//cpnet/page")
    if page_elem is not None:
        # ---------------------
        # 2a. Places
        # ---------------------
        for place_elem in page_elem.findall("place"):
            pid = place_elem.get("id", "")
            # The user-friendly name is typically from <text>
            text_elt = place_elem.find("text")
            place_name = text_elt.text.strip() if (text_elt is not None and text_elt.text) else pid
            place_id_to_name[pid] = place_name

            # find color set from <type><text> or <type><id>, or fallback
            color_set_name = "UnknownColorSet"
            type_elem = place_elem.find("type")
            if type_elem is not None:
                t_text_elt = type_elem.find("text")
                if t_text_elt is not None and t_text_elt.text:
                    color_set_name = t_text_elt.text.strip()
                else:
                    t_id_elt = type_elem.find("id")
                    if t_id_elt is not None and t_id_elt.text:
                        color_set_name = t_id_elt.text.strip()

            places.append({
                "name": place_name,
                "colorSet": color_set_name
            })

            # ---------- Initial Marking ----------
            initmark_elem = place_elem.find("initmark")
            if initmark_elem is not None:
                im_text_elt = initmark_elem.find("text")
                if im_text_elt is not None and im_text_elt.text:
                    marking_expr = im_text_elt.text.strip()
                    place_tokens, place_timestamps = parse_marking_expr(marking_expr)
                    if place_tokens:
                        if any(ts != 0.0 for ts in place_timestamps):
                            initial_marking[place_name] = {
                                "tokens": place_tokens,
                                "timestamps": place_timestamps
                            }
                        else:
                            initial_marking[place_name] = {
                                "tokens": place_tokens
                            }

        # ---------------------
        # 2b. Transitions
        # ---------------------
        # We'll collect arcs in a separate structure, keyed by transition name
        for trans_elem in page_elem.findall("trans"):
            tid = trans_elem.get("id", "")
            text_elt = trans_elem.find("text")
            trans_name = text_elt.text.strip() if (text_elt is not None and text_elt.text) else tid
            trans_id_to_name[tid] = trans_name

        trans_arcs = {tn: {"inArcs": [], "outArcs": []} for tn in trans_id_to_name.values()}

        # ---------------------
        # 2c. Arcs (inArcs / outArcs)
        # ---------------------
        for arc_elem in page_elem.findall("arc"):
            orientation = arc_elem.get("orientation", "")  # "PtoT", "TtoP", "bothdir", ...
            placeend = arc_elem.find("placeend")
            transend = arc_elem.find("transend")
            if placeend is None or transend is None:
                continue

            place_idref = placeend.get("idref", "")
            trans_idref = transend.get("idref", "")

            # Expression from <annot><text>
            arc_expr = ""
            annot_elt = arc_elem.find("annot")
            if annot_elt is not None:
                text_sub = annot_elt.find("text")
                if text_sub is not None and text_sub.text:
                    arc_expr = text_sub.text.strip()

            place_name = place_id_to_name.get(place_idref, "UnknownPlace")
            trans_name = trans_id_to_name.get(trans_idref, "UnknownTrans")

            if orientation == "PtoT":
                trans_arcs[trans_name]["inArcs"].append({
                    "place": place_name,
                    "expression": arc_expr
                })
            elif orientation == "TtoP":
                trans_arcs[trans_name]["outArcs"].append({
                    "place": place_name,
                    "expression": arc_expr
                })
            elif orientation == "bothdir":
                # Treat it as both input and output arc if needed
                trans_arcs[trans_name]["inArcs"].append({
                    "place": place_name,
                    "expression": arc_expr
                })
                trans_arcs[trans_name]["outArcs"].append({
                    "place": place_name,
                    "expression": arc_expr
                })

        # Now build final "transitions" list,
        # including guard and variables from the XML (if present).
        for trans_elem in page_elem.findall("trans"):
            tid = trans_elem.get("id", "")
            tname = trans_id_to_name.get(tid, tid)

            # 1) Guard
            guard_text = ""
            cond_annot = trans_elem.find("./condition/annot/text")
            if cond_annot is not None and cond_annot.text:
                guard_text = cond_annot.text.strip()

            # 2) Variables (or action code) from <code><ml>
            variables_list = []
            code_ml_elem = trans_elem.find("./code/ml")
            if code_ml_elem is not None and code_ml_elem.text:
                # For simplicity, store each non-blank line as a separate "variable" entry.
                # Adjust to parse them more cleverly if needed.
                raw_ml = code_ml_elem.text.strip()
                variables_list = [ln.strip() for ln in raw_ml.splitlines() if ln.strip()]

            # 3) Arc info
            arcs_data = trans_arcs.get(tname, {"inArcs": [], "outArcs": []})

            transitions.append({
                "name": tname,
                "guard": guard_text,
                "variables": variables_list,
                "transitionDelay": 0,
                "inArcs": arcs_data["inArcs"],
                "outArcs": arcs_data["outArcs"]
            })

    # ------------------------------------------------------------------
    # 3. Build final dictionary
    # ------------------------------------------------------------------
    result = {
        "colorSets": color_sets,
        "places": places,
        "transitions": transitions,
        "initialMarking": initial_marking,
        "evaluationContext": evaluation_context
    }

    return result


# ----------------------------------------------------------------------
# Helper to parse an initial marking expression like:
#   1`(1,"XYZ")++1`(2,"Hello")@10
#   1`"foo" ++ 1`42
# Typically CPN style might have "1`(value)@time", etc.
# ----------------------------------------------------------------------
def parse_marking_expr(marking_expr: str) -> (List[Any], List[float]):
    """
    Naive parser for a CPN initial marking expression of the form
        1`(value)@time ++ 1`(value2) ...
    Returns (tokens_list, timestamps_list).

    This is *very simplistic* and may not handle nested parentheses or tricky quoting.
    Adjust as needed.
    """
    tokens_out = []
    times_out = []

    # 1) split by "++"
    parts = marking_expr.split("++")
    for part in parts:
        part = part.strip()
        # match "1`(stuff)@time" or "1`stuff"
        match = re.match(r"^\d*`(.+?)(?:@([\d.]+))?$", part)
        if match:
            raw_token = match.group(1).strip()
            raw_time = match.group(2)
            if raw_time is None:
                time_val = 0.0
            else:
                try:
                    time_val = float(raw_time)
                except ValueError:
                    time_val = 0.0
            token_obj = parse_single_token(raw_token)
            tokens_out.append(token_obj)
            times_out.append(time_val)
        else:
            # fallback: entire part as raw token
            tokens_out.append(part)
            times_out.append(0.0)

    return tokens_out, times_out


def parse_single_token(raw: str) -> Any:
    """
    Attempt to interpret the raw token string as:
      - a tuple like (1,"xyz")
      - a quoted string "hello"
      - an int or float
      - else fallback to string
    """
    raw = raw.strip()
    # check if it's a tuple: e.g. (1,"xyz")
    if raw.startswith("(") and raw.endswith(")"):
        inside = raw[1:-1].strip()
        subvals = split_args_respecting_quotes(inside)
        out_tuple = []
        for sv in subvals:
            out_tuple.append(parse_single_token(sv))
        return tuple(out_tuple)

    # If it starts with " or ', treat as string
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw.strip('"\'')
    # else try int
    try:
        return int(raw)
    except ValueError:
        pass
    # else try float
    try:
        return float(raw)
    except ValueError:
        pass

    # fallback
    return raw


def split_args_respecting_quotes(s: str) -> List[str]:
    """
    Utility to split a string by commas while ignoring commas inside quotes.
    E.g. (1,"hello, world",2) => ["1","\"hello, world\"", "2"]
    This is simplistic (no nested parentheses, etc.).
    """
    parts = []
    current = []
    in_quote: Optional[str] = None
    for ch in s:
        if in_quote is None:
            if ch in ('"', "'"):
                in_quote = ch
                current.append(ch)
            elif ch == ',':
                parts.append("".join(current).strip())
                current = []
            else:
                current.append(ch)
        else:
            # we are inside a quote
            current.append(ch)
            if ch == in_quote:
                in_quote = None
    if current:
        parts.append("".join(current).strip())
    return parts
