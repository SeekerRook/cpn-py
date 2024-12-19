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


# Example usage
if __name__ == "__main__":
    # Create a couple of CPN modules (these might be constructed as shown previously)
    cs_definitions = """
    colset INT = int timed;
    """
    parser = ColorSetParser()
    colorsets = parser.parse_definitions(cs_definitions)
    int_set = colorsets["INT"]

    # Module A
    cpn_A = CPN()
    pA = Place("P_A", int_set)
    tA = Transition("SubT", variables=["x"], guard="x > 0")  # This will be a substitution transition
    cpn_A.add_place(pA)
    cpn_A.add_transition(tA)

    # Module B (a submodule)
    cpn_B = CPN()
    pB_in = Place("P_B_in", int_set)
    pB_out = Place("P_B_out", int_set)
    tB = Transition("T_B", variables=["y"], guard="y < 100")
    cpn_B.add_place(pB_in)
    cpn_B.add_place(pB_out)
    cpn_B.add_transition(tB)

    # Create the HCPN and add the modules
    hcpn = HCPN()
    hcpn.add_module("A", cpn_A)
    hcpn.add_module("B", cpn_B)

    # Define a substitution transition in module A that references module B as a submodule
    hcpn.add_substitution("A", "SubT", "B")

    print(hcpn)
