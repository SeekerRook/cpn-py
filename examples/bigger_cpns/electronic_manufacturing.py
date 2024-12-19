import json
from cpnpy.cpn.cpn_imp import *   # Assuming this includes the classes CPN, Marking, etc.
from cpnpy.cpn.importer import import_cpn_from_json
from typing import Dict, Any
from copy import deepcopy
from jsonschema import validate
from jsonschema.exceptions import ValidationError


json_data = json.load(open("../../files/bigger_cpns/electronic_manufacturing.json", "r"))
schema = json.load(open("../../files/validation_schema.json", "r"))

try:
    validate(instance=json_data, schema=schema)
    print("JSON data is valid.")
except ValidationError as e:
    print("JSON data is invalid.")
    print(f"Error message: {e.message}")

# Import the CPN, its initial marking, and the evaluation context from the JSON
cpn, marking, context = import_cpn_from_json(json_data)
print(cpn)
print(marking)

from cpnpy.visualization.visualizer import CPNGraphViz

viz = CPNGraphViz()
viz.apply(cpn, marking, format="svg")
viz.view()

#marking = deepcopy(marking)
while True:
    found = False
    for t in cpn.transitions:
        if cpn.is_enabled(t, marking, context):
            cpn.fire_transition(t, marking, context)
            found = True
    if not found:
        break


viz = CPNGraphViz()
viz.apply(cpn, marking, format="svg")
viz.view()
