"""
This script parses an XML file and produces a very compact JSON structure
of the form:

{
  "tag1": {
    "attributes": ["attrA", "attrB", "attrC"],
    "children": ["childTag1", "childTag2"]
  },
  "tag2": {
    "attributes": [],
    "children": ["anotherTag", "somethingElse"]
  },
  ...
}

**Data Semantics**:
- The top-level keys are unique tag names in the document (e.g., "book", "chapter", "page").
- "attributes": The union of all attribute names found on that tag anywhere in the XML.
- "children": The union of all tag names that appear as direct children of that tag anywhere in the XML.
  For example, if in one part of the document <tagA> has child <foo>, and in another <tagA> has child <bar>,
  then the script records "children": ["bar", "foo"] (or some sorted order).

**What is NOT included**:
- Exact parent/child relationships beyond the knowledge that a tag can contain certain child tags.
  (We do NOT store the fact that tagA might appear multiple times in different places. We merge them.)
- Repetitions, nesting levels, text content, or any other node data beyond attributes and child tag names.
- Ordering of children.
"""

import sys
import json
import xml.etree.ElementTree as ET


def extract_minimal_structure(xml_file_path):
    """
    Parse the given XML file and return a dictionary of the form:

    {
      "tagName1": {
        "attributes": [ ... list of unique attributes for tagName1 ... ],
        "children": [ ... list of unique child tags of tagName1 ... ]
      },
      "tagName2": {...},
      ...
    }
    """
    tree = ET.parse(xml_file_path)
    root = tree.getroot()

    # A dictionary where each key is a tag name, and the value is another dict:
    # {
    #   "attributes": set([...]),
    #   "children": set([...])
    # }
    structure_info = {}

    def collect_info(element):
        tag = element.tag
        # Ensure we have a place to store info about this tag
        if tag not in structure_info:
            structure_info[tag] = {"attributes": set(), "children": set()}

        # Update the set of attributes for this tag
        structure_info[tag]["attributes"].update(element.attrib.keys())

        # Check children
        for child in element:
            structure_info[tag]["children"].add(child.tag)
            # Recursively collect info from child
            collect_info(child)

    # Collect info starting from root
    collect_info(root)

    # Convert sets to sorted lists for a more readable/consistent JSON output
    final_structure = {}
    for tag, info in structure_info.items():
        final_structure[tag] = {
            "attributes": sorted(info["attributes"]),
            "children": sorted(info["children"])
        }

    return final_structure
