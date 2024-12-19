import json
from cpnpy.cpn.cpn_imp import *   # Assuming this includes the classes CPN, Marking, etc.
from cpnpy.cpn.importer import import_cpn_from_json
from typing import Dict, Any
from copy import deepcopy


json_data = json.load(open("../../files/bigger_cpns/hospital.json", "r"))
schema = json.load(open("../../files/validation_schema.json", "r"))

# Import the CPN, its initial marking, and the evaluation context from the JSON
cpn, marking, context = import_cpn_from_json(json_data)

#print(cpn)
#print(marking)

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
