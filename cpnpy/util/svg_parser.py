import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Tuple


def parse_graphviz_svg(svg_path: str) -> Dict[str, Any]:
    """
    Parse an SVG file produced by Graphviz and return a dictionary with node and edge information.

    Dictionary Structure
    --------------------
    The returned dictionary has the following keys:

    {
      "nodes": [
        {
          "id": str,                # The internal id from <g id="nodeX" ...>
          "title": str,             # The node's <title> text (e.g. "P_Int")
          "labels": [str, ...],     # All text labels appearing in the node <g> (in order)
          "geometry": {
            # For an ellipse:
            "type": "ellipse",
            "cx": float,
            "cy": float,
            "rx": float,
            "ry": float
            # For a path:
            # "type": "path",
            # "d": <path commands string>
          },
          "text_positions": [
            (x: float, y: float),   # (x, y) coordinates for each text <text> element in the node
            ...
          ],
        },
        ...
      ],
      "edges": [
        {
          "id": str,                # The internal id from <g id="edgeX" ...>
          "title": str,             # The edge's <title> text (e.g. "P_Int->T")
          "labels": [str, ...],     # The textual labels on the edge (one or more lines)
          "text_positions": [
            (x: float, y: float),   # (x, y) coordinates for each text <text> element in the edge
            ...
          ],
          "path_d": str,            # The 'd' attribute from the <path> element describing the edge
          "polygon_points": str,    # The 'points' attribute from the <polygon> element (arrow tip)
          "source": str,           # Derived from the edge title, before the '->'
          "target": str,           # Derived from the edge title, after the '->'
        },
        ...
      ]
    }

    :param svg_path: The file path to the Graphviz-generated SVG file.
    :return: A dictionary containing two keys: "nodes" and "edges".
    """
    tree = ET.parse(svg_path)
    root = tree.getroot()

    # We'll store parsed info in this dictionary
    graph_dict = {
        "nodes": [],
        "edges": []
    }

    # Namespace sometimes needed if the SVG has default namespace
    # But usually, we can just ignore or handle it explicitly.
    # e.g. If needed, we can do: xmlns = "{http://www.w3.org/2000/svg}"
    # For clarity, we'll keep the direct approach:

    # Look for all top-level <g> elements with class="node" or class="edge"
    for g_element in root.findall(".//{*}g"):
        g_class = g_element.get("class", "")
        g_id = g_element.get("id", "")

        if "node" in g_class:
            # This is a node group
            node_info = {
                "id": g_id,
                "title": "",
                "labels": [],
                "geometry": {},
                "text_positions": []
            }

            # The <title> child should contain the node name
            title_elem = g_element.find("{*}title")
            if title_elem is not None:
                node_info["title"] = title_elem.text.strip()

            # We look for ellipse or path to store geometry
            ellipse_elem = g_element.find("{*}ellipse")
            path_elem = g_element.find("{*}path")

            if ellipse_elem is not None:
                # We store ellipse geometry
                node_info["geometry"]["type"] = "ellipse"
                node_info["geometry"]["cx"] = float(ellipse_elem.get("cx", "0"))
                node_info["geometry"]["cy"] = float(ellipse_elem.get("cy", "0"))
                node_info["geometry"]["rx"] = float(ellipse_elem.get("rx", "0"))
                node_info["geometry"]["ry"] = float(ellipse_elem.get("ry", "0"))
            elif path_elem is not None:
                # We store path geometry
                node_info["geometry"]["type"] = "path"
                node_info["geometry"]["d"] = path_elem.get("d", "")

            # Collect all <text> elements under this <g> for labels
            texts = g_element.findall("{*}text")
            for txt_elem in texts:
                txt = txt_elem.text if txt_elem.text else ""
                node_info["labels"].append(txt.strip())
                # Also store position
                x = float(txt_elem.get("x", "0"))
                y = float(txt_elem.get("y", "0"))
                node_info["text_positions"].append((x, y))

            graph_dict["nodes"].append(node_info)

        elif "edge" in g_class:
            # This is an edge group
            edge_info = {
                "id": g_id,
                "title": "",
                "labels": [],
                "text_positions": [],
                "path_d": "",
                "polygon_points": "",
                "source": "",
                "target": ""
            }

            # The <title> child should contain something like "P_Int->T"
            title_elem = g_element.find("{*}title")
            if title_elem is not None:
                edge_title = title_elem.text.strip()
                edge_info["title"] = edge_title
                # Attempt to parse "source->target" from the title
                if "->" in edge_title:
                    parts = edge_title.split("->")
                    edge_info["source"] = parts[0].strip()
                    edge_info["target"] = parts[1].strip()

            # The main path describing the edge
            path_elem = g_element.find("{*}path")
            if path_elem is not None:
                edge_info["path_d"] = path_elem.get("d", "")

            # The polygon (usually the arrow tip)
            polygon_elem = g_element.find("{*}polygon")
            if polygon_elem is not None:
                edge_info["polygon_points"] = polygon_elem.get("points", "")

            # Collect any <text> elements on the edge
            texts = g_element.findall("{*}text")
            for txt_elem in texts:
                txt = txt_elem.text if txt_elem.text else ""
                edge_info["labels"].append(txt.strip())
                # also store position
                x = float(txt_elem.get("x", "0"))
                y = float(txt_elem.get("y", "0"))
                edge_info["text_positions"].append((x, y))

            graph_dict["edges"].append(edge_info)

    return graph_dict
