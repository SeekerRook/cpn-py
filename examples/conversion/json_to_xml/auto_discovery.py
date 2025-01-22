import pm4py
from cpnpy.discovery import traditional as traditional_discovery
from cpnpy.cpn import exporter
from cpnpy.util.conversion import json_to_cpn_xml


json_path = "../../../auto_disc1.json"
xml_path = "../../../auto_disc1.cpn"


if __name__ == "__main__":
    log = pm4py.read_xes("../../../files/other/xes/running-example.xes")
    cpn, marking, context = traditional_discovery.apply(log, parameters={"enable_guards_discovery": False, "enable_timing_discovery": False})
    exporter.export_cpn_to_json(cpn, marking, context, json_path)
    json_to_cpn_xml.apply(json_path)

    xml = json_to_cpn_xml.apply(json_path)

    F = open(xml_path, "w")
    F.write(xml)
    F.close()
