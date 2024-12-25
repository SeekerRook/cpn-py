import pm4py
from frozendict import frozendict
from pm4py.objects.log.obj import EventLog
from pm4py.objects.petri_net.obj import PetriNet
from pm4py.algo.simulation.montecarlo.utils import replay
from cpnpy.util import rv_to_stri
from cpnpy.cpn.cpn_imp import *


def last_non_null(series):
    """
    Returns the last non-null value of a pandas Series.
    If all are null, returns None (or np.nan, depending on preference).
    """
    non_null = series.dropna()
    if not non_null.empty:
        return non_null.iloc[-1]
    else:
        return None  # or np.nan


def apply(log: EventLog, pro_disc_alg=pm4py.discover_petri_net_inductive, parameters: Optional[Dict[str, Any]] = None):
    if parameters is None:
        parameters = {}

    original_log_cases_in_im = parameters.get("original_log_cases_in_im", False)
    original_case_attributes = parameters.get("original_case_attributes", {"case:concept:name"})
    num_simulated_cases = parameters.get("num_simulated_cases", 1)

    log = pm4py.convert_to_dataframe(log)

    net, im, fm = pro_disc_alg(log, parameters)
    stochastic_map = replay.get_map_from_log_and_net(log, net, im, fm)
    stochastic_map = rv_to_stri.transform_transition_dict(stochastic_map)

    parser = ColorSetParser()
    c = parser.parse_definitions("colset C = dict timed;")["C"]

    cpn = CPN()
    dict_places = dict()
    dict_transitions = dict()

    for place in net.places:
        p = Place(str(place.name), c)
        dict_places[place.name] = p
        cpn.add_place(p)

    for trans in net.transitions:
        t = Transition(trans.label if trans.label is not None else "SILENT@" + str(trans.name), variables=["C"])
        dict_transitions[trans.name] = t
        cpn.add_transition(t)

    for arc in net.arcs:
        if isinstance(arc.source, PetriNet.Place):
            cpn.add_arc(Arc(dict_places[arc.source.name], dict_transitions[arc.target.name], "C"))
        else:
            trans = arc.source

            cpn.add_arc(Arc(dict_transitions[trans.name], dict_places[arc.target.name], "C" + stochastic_map[trans]))

    marking = Marking()
    for p in im:
        if original_log_cases_in_im:
            result_dict = log.groupby("case:concept:name").agg(last_non_null).to_dict(orient='index')

            lst = []
            for c, vv in result_dict.items():
                lst.append(frozendict({k: v for k, v in vv.items() if k in original_case_attributes}))
            marking.set_tokens(dict_places[p.name].name,
                               lst)
        else:

            marking.set_tokens(dict_places[p.name].name,
                               [frozendict({"case:concept:name": "CASE_" + str(i + 1)}) for i in
                                range(num_simulated_cases)])

    code = """
from scipy.stats import norm, uniform, expon, lognorm, gamma
    """
    context = EvaluationContext(user_code=code)

    return cpn, marking, context
