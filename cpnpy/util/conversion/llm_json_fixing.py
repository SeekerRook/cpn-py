import requests
import json

api_url = "https://api.deepseek.com/chat/completions"
model_name = "deepseek-reasoner"
api_key = open("../../../../api_deepseek.txt", "r").read().strip()


def fix_json(data):
    json0 = json.dumps(data, indent=2)

    schema = open("../../../files/validation_schema.json", "r").read()

    question = "Can you fix the following JSON according to the JSON schema? In particular, translate Standard ML expressions in Python.\n\nJSON:\n\n" + json0 + "\n\n\nSCHEMA:\n\n" + schema

    #question = "What is 2+2?"

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer "+api_key
    }

    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": question}],
    }

    response = requests.post(api_url, headers=headers, json=payload).json()
    response_message = response["choices"][0]["message"]["content"]

    response_message = response_message.split("```json")[-1]
    response_message = response_message.split("```")[0]

    return response_message


if __name__ == "__main__":
    from cpnpy.cpn import importer, exporter
    from cpnpy.util.conversion import cpn_xml_to_json

    cpn, marking, context = importer.import_cpn_from_json(cpn_xml_to_json.cpn_xml_to_json("../../../files/other/xml/mynet.cpn"))
    exporter.export_cpn_to_json(cpn, marking, context, "../../../output.json")

    stru = json.load(open("../../../output.json", "r"))

    stru2 = fix_json(stru)
    print(stru2)
