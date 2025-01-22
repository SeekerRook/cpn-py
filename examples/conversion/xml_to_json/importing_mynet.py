from cpnpy.util.conversion import cpn_xml_to_json
from cpnpy.cpn import importer
from cpnpy.visualization import visualizer
import json

json_path = "../../../prova.json"

if __name__ == "__main__":
    dct = cpn_xml_to_json.cpn_xml_to_json("../../../files/other/xml/mynet.cpn")
    json.dump(dct, open(json_path, "w"))

    dct = json.load(open(json_path, "r"))

    cpn, marking, context = importer.import_cpn_from_json(dct)
    print(cpn)
    print(marking)
    viz = visualizer.CPNGraphViz()
    viz.apply(cpn, marking, format="svg")
    viz.view()

    #t = list(cpn.transitions)[0]
    #cpn.fire_transition(t, marking, context)
    #cpn.fire_transition(t, marking, context)
    #cpn.fire_transition(t, marking, context)
    #viz = visualizer.CPNGraphViz()
    #viz.apply(cpn, marking, format="svg")
    #viz.view()
