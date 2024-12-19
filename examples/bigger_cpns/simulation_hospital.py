import json

import pm4py

from cpnpy.cpn.cpn_imp import *   # Assuming this includes the classes CPN, Marking, etc.
from cpnpy.cpn.importer import import_cpn_from_json
from typing import Dict, Any
from copy import deepcopy
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from cpnpy.simulation.ocel_simu import simulate_cpn_to_ocel


json_data = json.load(open("../../files/bigger_cpns/hospital.json", "r"))
schema = json.load(open("../../files/validation_schema.json", "r"))

try:
    validate(instance=json_data, schema=schema)
    print("JSON data is valid.")
except ValidationError as e:
    print("JSON data is invalid.")
    print(f"Error message: {e.message}")

# Import the CPN, its initial marking, and the evaluation context from the JSON
cpn, marking, context = import_cpn_from_json(json_data)

# from previous code, we have cpn, marking, and context
ocel = simulate_cpn_to_ocel(cpn, marking, context)

print(ocel.get_extended_table())

#pm4py.write_ocel2(ocel, "../../prova.xml")
