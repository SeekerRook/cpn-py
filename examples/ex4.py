import json
from jsonschema import validate
from jsonschema.exceptions import ValidationError

json_data = json.load(open("ex3.json", "r"))
schema = json.load(open("../util/validation_schema.json", "r"))

try:
    validate(instance=json_data, schema=schema)
    print("JSON data is valid.")
except ValidationError as e:
    print("JSON data is invalid.")
    print(f"Error message: {e.message}")
