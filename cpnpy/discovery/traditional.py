import pm4py
from pm4py.objects.log.obj import EventLog
from pm4py.objects.petri_net.obj import PetriNet
from cpnpy.cpn.cpn_imp import *


def apply(log: EventLog, pro_disc_alg=pm4py.discover_petri_net_inductive, parameters: Optional[Dict[str, Any]] = None):
    if parameters is None:
        parameters = {}

    net, im, fm = pro_disc_alg(log, parameters)
    parser = ColorSetParser()
    c = parser.parse_definitions("colset C = dict;")["C"]

    cpn = CPN()
    dict_places = dict()
    dict_transitions = dict()

    for place in net.places:
        p = Place(str(place.name), c)
        dict_places[place.name] = p
        cpn.add_place(p)

    for trans in net.transitions:
        t = Transition(trans.label if trans.label is not None else "SILENT@"+str(trans.name), variables=["C"])
        dict_transitions[trans.name] = t
        cpn.add_transition(t)

    for arc in net.arcs:
        if isinstance(arc.source, PetriNet.Place):
            cpn.add_arc(Arc(dict_places[arc.source.name], dict_transitions[arc.target.name], "C"))
        else:
            cpn.add_arc(Arc(dict_transitions[arc.source.name], dict_places[arc.target.name], "C"))

    marking = Marking()
    for p in im:
        marking.set_tokens(dict_places[p.name].name, [frozenset()])

    code = """
from scipy.stats import norm, uniform, expon, lognorm, gamma
    """
    context = EvaluationContext(user_code=code)

    return cpn, marking, context

