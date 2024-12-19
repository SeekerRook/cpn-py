import graphviz
import html
import tempfile
import os
from cpnpy.cpn.cpn_imp import *


class CPNGraphViz:
    def __init__(self):
        self.graph = None
        self.format = "pdf"
        self.temp_dir = tempfile.mkdtemp()  # temporary directory for outputs

    def apply(self, cpn: CPN, marking: Marking, format: str = "pdf"):
        """
        Create a Graphviz Digraph from the given CPN and marking.

        :param cpn: The CPN object (with places, transitions, arcs)
        :param marking: The Marking object (with current tokens)
        :param format: The desired output format (e.g., 'pdf', 'png', 'svg')
        """
        self.format = format
        self.graph = graphviz.Digraph(format=self.format, directory=self.temp_dir)
        self.graph.attr(rankdir="LR")

        # Add Places
        for place in cpn.places:
            # Retrieve tokens from marking
            ms = marking.get_multiset(place.name)
            # Escape tokens for safety
            token_str_list = []
            for tok in ms.tokens:
                val_repr = html.escape(str(tok.value))
                if tok.timestamp != 0:
                    token_str_list.append(f"{val_repr}@{tok.timestamp}")
                else:
                    token_str_list.append(val_repr)
            token_str = ", ".join(token_str_list)

            # Construct label
            if token_str_list:
                label = f"{place.name}\\nTokens: {token_str}"
            else:
                label = f"{place.name}\\n(No tokens)"

            self.graph.node(place.name,
                            label=label,
                            shape="ellipse",
                            style="filled",
                            fillcolor="#e0e0f0")

        # Add Transitions
        for transition in cpn.transitions:
            lines = [transition.name]
            if transition.guard_expr:
                lines.append(f"Guard: {transition.guard_expr}")
            if transition.variables:
                vars_str = ", ".join(transition.variables)
                lines.append(f"Vars: {vars_str}")
            if transition.transition_delay > 0:
                lines.append(f"Delay: {transition.transition_delay}")

            label = "\\n".join(lines)
            self.graph.node(transition.name,
                            label=html.escape(label),
                            shape="rectangle",
                            style="rounded,filled",
                            fillcolor="#ffe0e0")

        # Add Arcs
        for arc in cpn.arcs:
            source_name = arc.source.name if hasattr(arc.source, 'name') else arc.source
            target_name = arc.target.name if hasattr(arc.target, 'name') else arc.target
            arc_label = html.escape(str(arc.expression))
            self.graph.edge(source_name, target_name, label=arc_label)

        return self

    def view(self):
        """
        View the generated graph using the default system viewer.
        """
        if self.graph is None:
            raise RuntimeError("Graph not created. Call apply() first.")
        self.graph.view()

    def save(self, filename: str):
        """
        Save (render) the graph to a file.

        The file will be saved in the temporary directory.
        The 'filename' is a base name without path, the renderer will append the format and '-O' suffix.
        """
        if self.graph is None:
            raise RuntimeError("Graph not created. Call apply() first.")
        # Render the file in the temporary directory
        out_path = self.graph.render(filename=filename, cleanup=True)
        # Move the rendered file back to the current directory if needed
        base, ext = os.path.splitext(out_path)
        final_path = os.path.join(os.getcwd(), os.path.basename(out_path))
        if os.path.abspath(final_path) != os.path.abspath(out_path):
            os.rename(out_path, final_path)
        # Cleanup the temp directory if desired (optional)
        return final_path


# Example usage (you can adjust as needed):
if __name__ == "__main__":
    cs_definitions = """
    colset INT = int timed;
    """
    parser = ColorSetParser()
    colorsets = parser.parse_definitions(cs_definitions)

    int_set = colorsets["INT"]

    p1 = Place("P1", int_set)
    p2 = Place("P2", int_set)
    t1 = Transition("T1", guard="x > 10", variables=["x"], transition_delay=2)

    cpn = CPN()
    cpn.add_place(p1)
    cpn.add_place(p2)
    cpn.add_transition(t1)
    cpn.add_arc(Arc(p1, t1, "x"))
    cpn.add_arc(Arc(t1, p2, "x @+3"))

    marking = Marking()
    marking.set_tokens("P1", [5, 12])

    viz = CPNGraphViz().apply(cpn, marking, format="png")
    viz.view()
    # You can also call viz.view() to open the image
