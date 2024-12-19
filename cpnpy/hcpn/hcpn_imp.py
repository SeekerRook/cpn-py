from cpnpy.cpn.cpn_imp import *


class HCPN:
    """
    Hierarchical Coloured Petri Net (HCPN) structure composed of multiple CPN modules.
    Each module is a separate CPN instance.

    Features:
    - Add multiple modules (each a CPN).
    - Define substitution transitions: mapping a transition in a parent module to a submodule (another CPN).
    - Maintain port/socket relations and fusion sets at the HCPN level.
    """

    def __init__(self):
        # Dictionary to hold named modules (CPNs)
        self.modules: Dict[str, CPN] = {}

        # Substitution transitions:
        # A mapping of (parent_module_name, substitution_transition_name) -> submodule_name
        # This indicates which CPN acts as the submodule for the given substitution transition.
        self.substitutions: Dict[(str, str), str] = {}

        # Port-Socket and Fusion relations could be stored similarly:
        # self.port_socket_relations = ...
        # self.fusion_sets = ...

    def add_module(self, name: str, cpn: CPN):
        """
        Add a module (CPN) with a given name.
        """
        if name in self.modules:
            raise ValueError(f"Module with name {name} already exists.")
        self.modules[name] = cpn

    def add_substitution(self, parent_module_name: str, sub_transition_name: str, submodule_name: str):
        """
        Define that a transition in a parent CPN is actually a substitution transition,
        which references another CPN as a submodule.
        """
        if parent_module_name not in self.modules:
            raise ValueError(f"Parent module '{parent_module_name}' not found.")
        if submodule_name not in self.modules:
            raise ValueError(f"Submodule '{submodule_name}' not found.")

        parent_cpn = self.modules[parent_module_name]
        trans = parent_cpn.get_transition_by_name(sub_transition_name)
        if trans is None:
            raise ValueError(
                f"Substitution transition '{sub_transition_name}' not found in module '{parent_module_name}'.")

        # Record the substitution
        self.substitutions[(parent_module_name, sub_transition_name)] = submodule_name

    def get_module(self, name: str) -> Optional[CPN]:
        """
        Retrieve a module (CPN) by name.
        """
        return self.modules.get(name)

    def get_substitution_target(self, parent_module_name: str, sub_transition_name: str) -> Optional[str]:
        """
        Given a parent module and a substitution transition name, get the submodule name.
        """
        return self.substitutions.get((parent_module_name, sub_transition_name), None)

    def __repr__(self):
        lines = ["HCPN:"]
        for name, cpn in self.modules.items():
            lines.append(f"  Module '{name}': {repr(cpn)}")
        lines.append("Substitutions:")
        for (parent_mod, sub_trans), sub_mod in self.substitutions.items():
            lines.append(f"  {parent_mod}.{sub_trans} -> {sub_mod}")
        return "\n".join(lines)


if __name__ == "__main__":
    """
    In this complex example, we demonstrate a Hierarchical Coloured Petri Net (HCPN) composed of four modules: A, B, C, and D.
    We illustrate the concepts of substitution transitions and fusion sets, and show a chain of hierarchical references.

    Key Concepts:

    1. **Substitution Transition**:
       A substitution transition is a special transition within a higher-level module that does not have a direct firing rule 
       on its own. Instead, it "refers to" (or "expands into") another module (a submodule). When the parent module attempts 
       to fire this substitution transition, we instead look into the submodule. The tokens that enter the submodule via its 
       port places are processed according to the submodule's net structure. Once processing finishes, tokens can exit the 
       submodule and flow back into the parent module. This allows us to represent a complex system at multiple levels of 
       abstraction. For example:
         - Module A's substitution transition T_ASub references Module B. When firing T_ASub, we "unfold" B and process tokens there.
         - Module B similarly uses T_BSub to reference Module C, and C uses T_CSub to reference Module D, creating a 4-level hierarchy.

    2. **Fusion Set**:
       A fusion set is a mechanism for merging multiple places, potentially from different modules, into a single logical place.
       All places in a fusion set share the same marking: adding a token to one place also makes it available in all fused places.
       This is useful for modeling scenarios where multiple modules must directly share certain data or states without duplication.
       For example:
         - A.P_A_fused, B.P_B_in, and C.P_C_in might belong to the same fusion set. If a token arrives in A.P_A_fused, 
           it is simultaneously available in B.P_B_in and C.P_C_in.

    In this example:
    - **Module A** is the top-level module. It has:
      - P_A_start: initial tokens.
      - P_A_mid: a normal intermediate place.
      - P_A_fused: a place that is part of a fusion set.
      - T_A: a normal transition to process tokens from P_A_start to P_A_fused.
      - T_ASub: a substitution transition that references Module B.

    - **Module B** (referenced by A):
      - P_B_in: fused with A.P_A_fused and also with C.P_C_in (to show a shared fusion set across multiple modules).
      - P_B_pass: an intermediate place inside B.
      - T_B: a normal transition from P_B_in to P_B_pass.
      - T_BSub: a substitution transition referencing Module C.
        Tokens "go down" into module C through T_BSub.

    - **Module C** (referenced by B):
      - P_C_in: fused with A.P_A_fused and B.P_B_in (part of the same fusion set).
      - P_C_mid: a place that will be fused with a place in D, demonstrating another fusion set.
      - P_C_out: a normal place inside C.
      - T_C: a normal transition from P_C_in to P_C_mid.
      - T_CSub: a substitution transition referencing Module D.

    - **Module D** (lowest-level submodule referenced by C):
      - P_D_in: fused with C.P_C_mid (another fusion set).
      - P_D_out: a normal place inside D.
      - T_D: a normal transition from P_D_in to P_D_out.

    We assume:
    - All places have a timed INT colorset.
    - Tokens flow: A.P_A_start -> T_A -> A.P_A_fused (fused with B and C) -> ... down through substitutions B -> C -> D.
    - Eventually, tokens processed in D can be returned up the hierarchy by appropriate arcs (not fully shown here).

    The code below sets up the HCPN structure (modules A, B, C, D), their places, transitions, arcs, 
    and the substitution transitions and fusion sets. We then create an initial marking on A's start place.

    Please note that the classes CPN, Place, Transition, Arc, Marking, HCPN, ColorSetParser, etc., 
    are assumed to be defined as per the earlier code examples. Here we focus on constructing the scenario only.
    """

    # Assume we have:
    # - ColorSetParser and colorsets defined
    # - Classes: CPN, Place, Transition, Arc, Marking, HCPN all available from previous code.

    cs_definitions = """
    colset INT = int timed;
    """
    parser = ColorSetParser()
    colorsets = parser.parse_definitions(cs_definitions)
    int_set = colorsets["INT"]

    # --------------------------
    # MODULE D
    # --------------------------
    cpn_D = CPN()
    pD_in = Place("P_D_in", int_set)
    pD_out = Place("P_D_out", int_set)
    tD = Transition("T_D", variables=["d"], guard="d >= 0", transition_delay=1)

    cpn_D.add_place(pD_in)
    cpn_D.add_place(pD_out)
    cpn_D.add_transition(tD)
    cpn_D.add_arc(Arc(pD_in, tD, "d"))
    cpn_D.add_arc(Arc(tD, pD_out, "d+5"))

    # --------------------------
    # MODULE C
    # --------------------------
    cpn_C = CPN()
    pC_in = Place("P_C_in", int_set)     # fused with A.P_A_fused and B.P_B_in
    pC_mid = Place("P_C_mid", int_set)   # fused with D.P_D_in
    pC_out = Place("P_C_out", int_set)
    tC = Transition("T_C", variables=["c"], guard="c < 100", transition_delay=0)
    tCSub = Transition("T_CSub", variables=["c2"])  # references D

    cpn_C.add_place(pC_in)
    cpn_C.add_place(pC_mid)
    cpn_C.add_place(pC_out)
    cpn_C.add_transition(tC)
    cpn_C.add_transition(tCSub)

    # Normal arc: C_in -> T_C -> C_mid
    cpn_C.add_arc(Arc(pC_in, tC, "c"))
    cpn_C.add_arc(Arc(tC, pC_mid, "c+10"))

    # Substitution arcs: C_mid -> T_CSub -> C_out
    # This shows we send tokens from C_mid into the submodule D and then out again.
    cpn_C.add_arc(Arc(pC_mid, tCSub, "c2"))    # from fused place to T_CSub
    cpn_C.add_arc(Arc(tCSub, pC_out, "c2*2"))  # double the token value coming out of D (conceptually)

    # --------------------------
    # MODULE B
    # --------------------------
    cpn_B = CPN()
    pB_in = Place("P_B_in", int_set)   # fused with A.P_A_fused and C.P_C_in
    pB_pass = Place("P_B_pass", int_set)
    tB = Transition("T_B", variables=["b"], guard="b >= 0", transition_delay=2)
    tBSub = Transition("T_BSub", variables=["b2"])  # references C

    cpn_B.add_place(pB_in)
    cpn_B.add_place(pB_pass)
    cpn_B.add_transition(tB)
    cpn_B.add_transition(tBSub)

    # Normal arc: B_in -> T_B -> B_pass
    cpn_B.add_arc(Arc(pB_in, tB, "b"))
    cpn_B.add_arc(Arc(tB, pB_pass, "b+1"))

    # Substitution arcs: B_pass -> T_BSub and T_BSub -> B_in (we can cycle back for complexity)
    # Here we show that tokens can go down into C and come back up.
    cpn_B.add_arc(Arc(pB_pass, tBSub, "b2"))
    # For simplicity, let's say after going through C, tokens re-enter B_in
    # (In a real scenario, you'd map ports differently. This creates a cycle for demonstration.)
    cpn_B.add_arc(Arc(tBSub, pB_in, "b2-5"))

    # --------------------------
    # MODULE A (top-level)
    # --------------------------
    cpn_A = CPN()
    pA_start = Place("P_A_start", int_set)
    pA_mid = Place("P_A_mid", int_set)
    pA_fused = Place("P_A_fused", int_set)  # fused with B.P_B_in and C.P_C_in
    tA = Transition("T_A", variables=["a"], guard="a >= 0", transition_delay=0)
    tASub = Transition("T_ASub", variables=["a2"])  # references B

    cpn_A.add_place(pA_start)
    cpn_A.add_place(pA_mid)
    cpn_A.add_place(pA_fused)
    cpn_A.add_transition(tA)
    cpn_A.add_transition(tASub)

    # Normal arc: A_start -> T_A -> A_fused
    cpn_A.add_arc(Arc(pA_start, tA, "a"))
    cpn_A.add_arc(Arc(tA, pA_fused, "a*2"))

    # Substitution arcs: A_fused -> T_ASub -> A_mid
    # Tokens go down into B (and subsequently into C and D), then come back up to A_mid.
    cpn_A.add_arc(Arc(pA_fused, tASub, "a2"))
    cpn_A.add_arc(Arc(tASub, pA_mid, "a2+3"))

    # --------------------------
    # HCPN Setup
    # --------------------------
    hcpn = HCPN()
    hcpn.add_module("A", cpn_A)
    hcpn.add_module("B", cpn_B)
    hcpn.add_module("C", cpn_C)
    hcpn.add_module("D", cpn_D)

    # Set up the chain of substitutions:
    # A.T_ASub -> B
    # B.T_BSub -> C
    # C.T_CSub -> D
    hcpn.add_substitution("A", "T_ASub", "B")
    hcpn.add_substitution("B", "T_BSub", "C")
    hcpn.add_substitution("C", "T_CSub", "D")

    # Define fusion sets (conceptually, if HCPN supports them):
    # Fusion Set 1: A.P_A_fused, B.P_B_in, C.P_C_in
    # Fusion Set 2: C.P_C_mid, D.P_D_in
    # (In practice, you'd have something like hcpn.add_fusion_set([...]) if implemented.)
    # hcpn.add_fusion_set(["A.P_A_fused", "B.P_B_in", "C.P_C_in"])
    # hcpn.add_fusion_set(["C.P_C_mid", "D.P_D_in"])

    # Initial marking:
    # Start with tokens in A.P_A_start: [0, 10, 20]
    marking = Marking()
    marking.set_tokens("P_A_start", [0, 10, 20])

    # Print structure and initial marking
    print(hcpn)
    print("Initial Marking:")
    print(marking)

    # This sets the stage for a complex hierarchical scenario. Actual firing and simulation would:
    # - Fire T_A in A, moving tokens into the fused set places.
    # - Use T_ASub to go into B, then T_BSub to go into C, then T_CSub into D.
    # - Tokens processed at lower levels return up, influenced by guards, delays, and arithmetic in arc expressions.
    # - Fusion sets ensure places across modules share the same markings.
