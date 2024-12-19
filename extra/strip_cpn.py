input_file = r"C:\Users\berti\masterthesis-code\Evaluation\Process Models and Event Logs\Hiring\Models\Hiring_Model_High_Settings.cpn"
output_file = "hiring.cpn"

import xml.etree.ElementTree as ET
import sys


def remove_elements(root, names_to_remove, tag_to_remove):
    """
    Recursively remove elements whose 'name' attribute is in names_to_remove
    OR whose tag matches tag_to_remove.
    """
    to_remove = []
    for child in root:
        child_name = child.attrib.get('name', None)
        # Check if the element should be removed by name or by tag
        if child.tag == tag_to_remove or child_name in names_to_remove:
            to_remove.append(child)
        else:
            # Recurse into child elements
            remove_elements(child, names_to_remove, tag_to_remove)

    # Remove collected elements
    for elem in to_remove:
        root.remove(elem)


if __name__ == "__main__":
    # The names of elements we want to remove and the tag we want to remove
    names_to_remove = {"posattr", "fillattr", "lineattr", "textattr"}
    tag_to_remove = "IndexNode"

    # Parse the input XML
    tree = ET.parse(input_file)
    root = tree.getroot()

    # Remove elements
    remove_elements(root, names_to_remove, tag_to_remove)

    # Write the modified tree back to a file
    tree.write(output_file, encoding='utf-8', xml_declaration=True)
