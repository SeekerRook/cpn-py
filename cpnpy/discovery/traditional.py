import random

import pm4py
from frozendict import frozendict
from pm4py.objects.log.obj import EventLog
from pm4py.objects.petri_net.obj import PetriNet
from cpnpy.util import rv_to_stri
from typing import Tuple
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


def apply(log: EventLog, parameters: Optional[Dict[str, Any]] = None) -> Tuple[CPN, Marking, EvaluationContext]:
    """
    Applies a process discovery algorithm to the input event log, optionally discovers guards for transitions
    using decision mining, and constructs a colored Petri net (CPN) with a corresponding initial marking
    and context for stochastic behavior.

    This function performs the following steps:
    1. Discovers an accepting Petri net (and its initial and final markings) from the provided event log
       using the chosen process discovery algorithm.
    2. Optionally applies decision mining to discover transition guards (boolean expressions) that
       regulate the transitions based on case attributes.
    3. Constructs a colored Petri net where:
       - Each Petri net place is mapped to a CPN place.
       - Each Petri net transition is mapped to a CPN transition, optionally decorated with the discovered guard.
       - Arcs may include timing delays derived from the event log's timestamps (stochastic behavior).
    4. Creates an initial marking where token dictionaries hold selected case attributes. If
       `original_log_cases_in_im` is enabled, it samples actual cases from the log to populate the marking;
       otherwise, it creates a predefined number of artificial cases.
    5. Returns a tuple containing the constructed CPN, the initial marking, and a context that allows
       the evaluation of stochastic distributions.

    Parameters
    ----------
    log : pm4py.objects.log.obj.EventLog
        The input event log to be converted into a colored Petri net.
    parameters : Dict[str, Any], optional
        A dictionary of configuration parameters controlling discovery and transformation steps. Supported keys:
        - num_simulated_cases (int): Number of initial tokens (cases) to include in the initial marking
          (default: 1).
        - pro_disc_alg (Callable): Function used to discover the Petri net from the event log
          (default: pm4py.discover_petri_net_inductive).
        - original_case_attributes (Set[str]): Set of attributes that will be included in each token for guard
          expressions or analysis (default: {"case:concept:name"}).
        - enable_guards_discovery (bool): If True, decision mining is applied to discover guards on transitions
          (default: False).
        - original_log_cases_in_im (bool): If True, the function samples real cases from the original log to
          populate the initial marking. If False, it creates artificial case tokens (default: True if any guard
          is discovered, otherwise False).

    Returns
    -------
    cpn : cpnpy.cpn.cpn_imp.CPN
        The constructed colored Petri net, including places, transitions, and arcs with optional delays/guards.
    marking : cpnpy.cpn.cpn_imp.Marking
        The initial marking of the colored Petri net, populated with token dictionaries representing case attributes.
    context : cpnpy.cpn.cpn_imp.EvaluationContext
        A context that includes definitions for evaluating stochastic distributions within the colored Petri net.
    """
    if parameters is None:
        parameters = {}

    num_simulated_cases = parameters.get("num_simulated_cases", 1)
    pro_disc_alg = parameters.get("pro_disc_alg", pm4py.discover_petri_net_inductive)
    original_case_attributes = parameters.get("original_case_attributes", {"case:concept:name"})
    enable_guards_discovery = parameters.get("enable_guards_discovery", False)
    enable_timing_discovery = parameters.get("enable_timing_discovery", True)

    log = pm4py.convert_to_dataframe(log)

    # applies a process discovery algorithm in pm4py, discovering an accepting Petri net from a traditional event log
    net, im, fm = pro_disc_alg(log, parameters)
    if enable_guards_discovery:
        from pm4py.algo.decision_mining import algorithm as decision_mining

        # if the discovery of the guards is enabled, discover the guards on the transitions
        # (conditions regulating the execution).
        net, im, fm = decision_mining.create_data_petri_nets_with_decisions(log, net, im, fm)

    stochastic_map = {}
    if enable_timing_discovery:
        from pm4py.algo.simulation.montecarlo.utils import replay

        # discovers a stochastic map, associating each transition of the original accepting Petri net with a stochastic
        # variable indicating the delay
        stochastic_map = replay.get_map_from_log_and_net(log, net, im, fm)
        # transforms the stochastic variables inside the map into arc delayed in the notation used for cpnpy.
        stochastic_map = rv_to_stri.transform_transition_dict(stochastic_map)

    # create a single color set (representing the case level attributes)
    parser = ColorSetParser()
    c = parser.parse_definitions("colset C = dict timed;")["C"]

    cpn = CPN()
    dict_places = dict()
    dict_transitions = dict()

    for place in net.places:
        p = Place(str(place.name), c)
        dict_places[place.name] = p
        cpn.add_place(p)

    trans_guards = {}
    for trans in net.transitions:
        if "guard" in trans.properties:
            from cpnpy.util import simp_guard
            eval = simp_guard.parse_boolean_expression(trans.properties["guard"],
                                                       variables_of_interest=list(original_case_attributes))
            if str(eval) != "True":
                trans_guards[trans.name] = str(eval)

    if trans_guards:
        #print(trans_guards)
        #input()
        pass

    # include in the initial marking the case attributes from the original cases of the event log
    # enabled by default when the guards are discovered from the event log
    original_log_cases_in_im = parameters.get("original_log_cases_in_im", len(trans_guards) > 0)

    for trans in net.transitions:
        guard = None
        if trans.name in trans_guards:
            guard = trans_guards[trans.name]
            for att in original_case_attributes:
                guard = guard.replace(att, "C[\"" + att + "\"]")
                pass

        t = Transition(trans.label if trans.label is not None else "SILENT@" + str(trans.name), variables=["C"],
                       guard=guard)
        dict_transitions[trans.name] = t
        cpn.add_transition(t)

    for arc in net.arcs:
        if isinstance(arc.source, PetriNet.Place):
            cpn.add_arc(Arc(dict_places[arc.source.name], dict_transitions[arc.target.name], "C"))
        else:
            trans = arc.source
            if trans in stochastic_map:
                cpn.add_arc(
                    Arc(dict_transitions[trans.name], dict_places[arc.target.name], "C" + stochastic_map[trans]))
            else:
                cpn.add_arc(Arc(dict_transitions[trans.name], dict_places[arc.target.name], "C"))

    marking = Marking()
    for p in im:
        if original_log_cases_in_im:
            all_cases = set(log["case:concept:name"].unique())
            all_cases = set(random.sample(all_cases, min(len(all_cases), num_simulated_cases)))
            result_dict = log[log["case:concept:name"].isin(all_cases)].groupby("case:concept:name").agg(last_non_null).to_dict(orient='index')

            lst = []
            for c, vv in result_dict.items():
                lst.append(frozendict({k: v for k, v in vv.items() if k in original_case_attributes}))
            marking.set_tokens(dict_places[p.name].name,
                               lst)
        else:

            marking.set_tokens(dict_places[p.name].name,
                               [frozendict({"case:concept:name": "CASE_" + str(i + 1)}) for i in
                                range(num_simulated_cases)])

    code = ""
    if enable_timing_discovery:
        code = """
    from scipy.stats import norm, uniform, expon, lognorm, gamma
        """
    context = EvaluationContext(user_code=code)

    return cpn, marking, context
