import time
import networkx as nx
from typing import Tuple

from cpnpy.analysis.reachability import build_reachability_graph
from cpnpy.analysis.scc import build_scc_graph
from cpnpy.cpn.cpn_imp import *


class StateSpaceAnalyzer:
    def __init__(self, cpn, marking, context=None):
        """
        Initialize the analyzer with the given CPN.
        The constructor will:
          - Build the reachability graph (RG) from the CPN's initial marking and context.
          - Build the SCC graph (SG) from the RG.
        """
        if context is None:
            context = EvaluationContext(user_code="")

        self.cpn = cpn
        self.marking = marking
        self.context = context

        # Compute the reachability graph
        self.RG = build_reachability_graph(self.cpn, self.marking, self.context)
        # Compute the SCC graph
        self.SG = build_scc_graph(self.RG)

        # Precompute transitions enabled at each marking to speed up analyses
        self.marking_to_enabled_transitions = {}
        self._precompute_enabled_transitions()

        # Internal attributes to store computation times if needed
        self._compute_statistics_time = None
        self._compute_bounds_time = None

    def _precompute_enabled_transitions(self):
        """Precompute which transitions are enabled at each marking."""
        for node in self.RG.nodes():
            marking = self.RG.nodes[node]['marking']
            enabled = []
            # Find all enabled transitions by checking for any valid binding
            for t in self.cpn.transitions:
                bindings = self.cpn._find_all_bindings(t, marking, self.context)
                if bindings:
                    enabled.append(t.name)
            self.marking_to_enabled_transitions[node] = enabled

    # --------------------------------------------------------------------------
    # Statistics
    # --------------------------------------------------------------------------
    def get_statistics(self) -> Dict[str, Any]:
        """
        Returns statistics about the state space and SCC graph.
        """
        start = time.time()
        stats = {
            "RG_nodes": self.RG.number_of_nodes(),
            "RG_arcs": self.RG.number_of_edges(),
            "SCC_nodes": self.SG.number_of_nodes(),
            "SCC_arcs": self.SG.number_of_edges()
        }
        end = time.time()
        stats["computation_time"] = end - start
        self._compute_statistics_time = stats["computation_time"]
        return stats

    # --------------------------------------------------------------------------
    # Reachability
    # --------------------------------------------------------------------------
    def is_reachable(self, from_node, to_node) -> bool:
        """
        Check if to_node is reachable from from_node in the RG.
        """
        return nx.has_path(self.RG, from_node, to_node)

    # --------------------------------------------------------------------------
    # Boundedness
    # --------------------------------------------------------------------------
    def get_place_bounds(self) -> Dict[str, Tuple[int, int]]:
        """
        Compute min and max token counts for each place.
        Returns {place_name: (min_tokens, max_tokens)}.
        """
        start = time.time()
        place_names = [p.name for p in self.cpn.places]
        place_min = {p: float('inf') for p in place_names}
        place_max = {p: 0 for p in place_names}

        for node in self.RG.nodes():
            marking = self.RG.nodes[node]['marking']
            for p in place_names:
                count = len(marking.get_multiset(p).tokens)
                if count < place_min[p]:
                    place_min[p] = count
                if count > place_max[p]:
                    place_max[p] = count

        for p in place_names:
            if place_min[p] == float('inf'):
                place_min[p] = 0

        end = time.time()
        self._compute_bounds_time = end - start
        return {p: (place_min[p], place_max[p]) for p in place_names}

    def get_place_multiset_bounds(self) -> Dict[str, Dict[Any, Tuple[int, int]]]:
        """
        Compute min and max count for each distinct token value per place.
        Returns {place_name: {token_value: (min_count, max_count)}}.
        """
        place_names = [p.name for p in self.cpn.places]
        token_stats = {p: {} for p in place_names}

        for node in self.RG.nodes():
            marking = self.RG.nodes[node]['marking']
            for p in place_names:
                ms = marking.get_multiset(p)
                val_counts = {}
                for tok in ms.tokens:
                    val_counts[tok.value] = val_counts.get(tok.value, 0) + 1

                # Update token_stats
                for val, c in val_counts.items():
                    if val not in token_stats[p]:
                        token_stats[p][val] = [c, c]
                    else:
                        if c < token_stats[p][val][0]:
                            token_stats[p][val][0] = c
                        if c > token_stats[p][val][1]:
                            token_stats[p][val][1] = c

                # Check for values not appearing in this marking
                all_vals_seen = set(token_stats[p].keys())
                for val in all_vals_seen:
                    if val not in val_counts:
                        if 0 < token_stats[p][val][0]:
                            token_stats[p][val][0] = 0

        # Convert lists to tuples
        for p in token_stats:
            for val in token_stats[p]:
                token_stats[p][val] = tuple(token_stats[p][val])

        return token_stats

    # --------------------------------------------------------------------------
    # Home Properties
    # --------------------------------------------------------------------------
    def list_home_markings(self) -> List[Any]:
        """
        Returns home markings. If there's a unique terminal SCC, all states in it are home.
        """
        terminal_sccs = [n for n in self.SG.nodes() if self.SG.out_degree(n) == 0]
        if len(terminal_sccs) == 1:
            scc_node = terminal_sccs[0]
            members = self.SG.nodes[scc_node]['members']
            return list(members)
        return []

    # --------------------------------------------------------------------------
    # Liveness
    # --------------------------------------------------------------------------
    def list_dead_markings(self) -> List[Any]:
        """Markings with no enabled transitions."""
        return [node for node, ets in self.marking_to_enabled_transitions.items() if not ets]

    def list_dead_transitions(self) -> List[str]:
        """Transitions that are never enabled."""
        all_ts = {t.name for t in self.cpn.transitions}
        occurred = set()
        for ets in self.marking_to_enabled_transitions.values():
            occurred.update(ets)
        return list(all_ts - occurred)

    def list_live_transitions(self) -> List[str]:
        """Transitions that appear in all terminal SCCs (a heuristic for liveness)."""
        terminal_sccs = [n for n in self.SG.nodes() if self.SG.out_degree(n) == 0]

        if not terminal_sccs:
            return [t.name for t in self.cpn.transitions]

        def transitions_in_scc(scc_node):
            members = self.SG.nodes[scc_node]['members']
            ts = set()
            for m in members:
                ts.update(self.marking_to_enabled_transitions[m])
            return ts

        scc_transitions = [transitions_in_scc(s) for s in terminal_sccs]
        common = set.intersection(*scc_transitions) if scc_transitions else set()
        return list(common)

    # --------------------------------------------------------------------------
    # Fairness
    # --------------------------------------------------------------------------
    def list_impartial_transitions(self) -> List[str]:
        """Impartial transitions: occur infinitely often in all infinite occurrence sequences (heuristic)."""
        terminal_sccs = [n for n in self.SG.nodes() if self.SG.out_degree(n) == 0]

        if not terminal_sccs:
            return []

        def transitions_in_scc(scc_node):
            members = self.SG.nodes[scc_node]['members']
            ts = set()
            for m in members:
                ts.update(self.marking_to_enabled_transitions[m])
            return ts

        scc_transitions = [transitions_in_scc(s) for s in terminal_sccs]
        common = set.intersection(*scc_transitions) if scc_transitions else set()
        return list(common)

    # --------------------------------------------------------------------------
    # Summary
    # --------------------------------------------------------------------------
    def summarize(self) -> Dict[str, Any]:
        """
        Produce a summary report of various properties.
        """
        stats = self.get_statistics()
        place_bounds = self.get_place_bounds()
        dead_markings = self.list_dead_markings()
        dead_transitions = self.list_dead_transitions()
        live_transitions = self.list_live_transitions()
        impartial_transitions = self.list_impartial_transitions()
        home_markings = self.list_home_markings()

        return {
            "statistics": stats,
            "place_bounds": place_bounds,
            "dead_markings": dead_markings,
            "dead_transitions": dead_transitions,
            "live_transitions": live_transitions,
            "impartial_transitions": impartial_transitions,
            "home_markings": home_markings,
        }


if __name__ == "__main__":
    # Example with timed color sets
    cs_definitions = """
    colset INT = int timed;
    colset STRING = string;
    colset PAIR = product(INT, STRING) timed;
    """

    parser = ColorSetParser()
    colorsets = parser.parse_definitions(cs_definitions)

    int_set = colorsets["INT"]
    pair_set = colorsets["PAIR"]

    # Create the CPN structure
    p_int = Place("P_Int", int_set)  # timed place
    p_pair = Place("P_Pair", pair_set)  # timed place
    # Added transition_delay=2 as an example
    t = Transition("T", guard="x > 10", variables=["x"], transition_delay=2)

    cpn = CPN()
    cpn.add_place(p_int)
    cpn.add_place(p_pair)
    # Arc with time delay on output: produced tokens get timestamp = global_clock + transition_delay + arc_delay
    cpn.add_transition(t)
    cpn.add_arc(Arc(p_int, t, "x"))
    cpn.add_arc(Arc(t, p_pair, "(x, 'hello') @+5"))

    # Create a marking
    marking = Marking()
    marking.set_tokens("P_Int", [5, 12])  # both at timestamp 0
    print(cpn)
    print(marking)

    user_code = """
def double(n):
    return n*2
    """
    context = EvaluationContext(user_code=user_code)

    # Now, construct the StateSpaceAnalyzer and call its methods
    analyzer = StateSpaceAnalyzer(cpn, marking, context)
    report = analyzer.summarize()

    print("=== State Space Report ===")
    for key, val in report.items():
        print(f"{key}: {val}")
