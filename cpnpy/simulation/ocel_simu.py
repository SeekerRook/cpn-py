import copy
import pandas as pd
from cpnpy.cpn.cpn_imp import *
from pm4py.objects.ocel.obj import OCEL


def simulate_cpn_to_ocel(cpn: CPN, initial_marking: Marking, context: EvaluationContext) -> OCEL:
    """
    Simulate the given CPN starting from the given initial marking, and return an OCEL object.
    Each fired transition is recorded as an event.
    Input and output tokens for each event are considered as related objects.
    """
    marking = copy.deepcopy(initial_marking)

    # Data structures to build the OCEL
    event_list = []
    object_set = set()
    relation_list = []

    event_counter = 1

    # Helper to guess object type from a place or other logic
    def get_object_type(place_name: str) -> str:
        return f"type_{place_name}"

    # Helper to safely get object ID as a hashable value (stringify non-hashable objects)
    def make_object_id(value):
        # If it's not hashable, convert to string
        # Or simply always convert to string to ensure consistent behavior
        if isinstance(value, list) or isinstance(value, dict) or isinstance(value, set) or isinstance(value, tuple):
            return str(value)
        return str(value)

    # Run simulation until no transition is enabled
    while True:
        enabled_transitions = []
        # Check which transitions are enabled
        for t in cpn.transitions:
            if cpn.is_enabled(t, marking, context):
                enabled_transitions.append(t)

        if not enabled_transitions:
            # No transitions enabled, try to advance time
            old_clock = marking.global_clock
            cpn.advance_global_clock(marking)
            if marking.global_clock == old_clock:
                # No advancement in time means we are done
                break
            else:
                # After advancing clock, check again
                continue

        # Fire an arbitrary enabled transition (or define a selection strategy)
        t = enabled_transitions[0]

        # Determine the actual binding used to fire
        binding = cpn._find_binding(t, marking, context)
        if binding is None:
            # If no binding found, skip (this should not normally happen since we checked is_enabled)
            break

        # Add a minuscule increment to the event timestamp to preserve ordering
        # even if multiple events occur at the same logical time.
        # Here, we add a microsecond per event.
        event_timestamp = pd.to_datetime(marking.global_clock, unit='s', utc=True) + pd.to_timedelta(event_counter,
                                                                                                     unit='us')

        # The activity is the transition name
        activity = t.name

        # Identify related objects from input and output arcs
        related_objects = set()

        # For input arcs, tokens to be removed are the input objects
        for arc in cpn.get_input_arcs(t):
            values, _ = context.evaluate_arc(arc.expression, binding)
            for v in values:
                obj_id = make_object_id(v)
                otype = get_object_type(arc.source.name)
                related_objects.add((obj_id, otype))

        # Fire transition (this will modify the marking)
        cpn.fire_transition(t, marking, context, binding)

        # For output arcs, tokens added are related objects too
        for arc in cpn.get_output_arcs(t):
            values, arc_delay = context.evaluate_arc(arc.expression, binding)
            for v in values:
                obj_id = make_object_id(v)
                otype = get_object_type(arc.target.name)
                related_objects.add((obj_id, otype))

        # Event ID
        eid = f"e_{event_counter}"
        event_counter += 1

        # Add event to event_list
        event_list.append({
            "ocel:eid": eid,
            "ocel:activity": activity,
            "ocel:timestamp": event_timestamp
        })

        # Add objects and relations
        for (oid, otype) in related_objects:
            object_set.add((oid, otype))
            relation_list.append({
                "ocel:eid": eid,
                "ocel:activity": activity,
                "ocel:timestamp": event_timestamp,
                "ocel:oid": oid,
                "ocel:type": otype,
                "ocel:qualifier": None
            })

    # Create dataframes
    events_df = pd.DataFrame(event_list)
    objects_df = pd.DataFrame([
        {"ocel:oid": oid, "ocel:type": otype}
        for (oid, otype) in object_set
    ])
    relations_df = pd.DataFrame(relation_list)

    # Create OCEL object
    ocel = OCEL(
        events=events_df,
        objects=objects_df,
        relations=relations_df
    )

    return ocel
