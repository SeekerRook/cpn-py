import re
import sympy
from sympy import And, Or, Eq, Lt, Le, Gt, Ge


def parse_comparison(comp_str, symbol_table, treat_inf_as_symbol=True):
    """
    Parse a single comparison like "amount <= inf" or "x > 0.5" into a Sympy
    relational expression. `symbol_table` is a dict for looking up/creating Sympy symbols.
    If `treat_inf_as_symbol` is True, the string 'inf' is treated as a symbol named 'inf'.
    Otherwise, you can treat it as float('inf') or a large numeric constant.
    """
    pattern = r'^\s*(.*?)\s*(<=|>=|<|>|==|=)\s*(.*?)\s*$'
    match = re.match(pattern, comp_str)
    if not match:
        raise ValueError(f"Cannot parse comparison: {comp_str}")

    left_str, op, right_str = match.groups()
    left_str = left_str.strip()
    right_str = right_str.strip()

    # Normalize '=' or '==' into '=='
    if op in ['=', '==']:
        op = '=='

    left_expr = _to_symbol_or_number(left_str, symbol_table, treat_inf_as_symbol)
    right_expr = _to_symbol_or_number(right_str, symbol_table, treat_inf_as_symbol)

    if op == '<=':
        return Le(left_expr, right_expr)
    elif op == '<':
        return Lt(left_expr, right_expr)
    elif op == '>=':
        return Ge(left_expr, right_expr)
    elif op == '>':
        return Gt(left_expr, right_expr)
    elif op == '==':
        return Eq(left_expr, right_expr)
    else:
        raise ValueError(f"Unsupported operator: {op}")


def _to_symbol_or_number(token_str, symbol_table, treat_inf_as_symbol):
    """
    Helper to convert a token string to either a float, or a Sympy symbol.
    - If token_str can be float(...), do so.
    - If token_str == 'inf' and treat_inf_as_symbol=True, return symbol_table['inf'].
      Otherwise, use float('inf') or sympy.oo, etc.
    - Otherwise, treat it as a variable name and return symbol_table[var].
    """
    # Try to parse as float
    try:
        return float(token_str)
    except ValueError:
        pass

    # Check for 'inf'
    if token_str == 'inf':
        if treat_inf_as_symbol:
            if token_str not in symbol_table:
                symbol_table[token_str] = sympy.Symbol(token_str, real=True)
            return symbol_table[token_str]
        else:
            return sympy.oo  # treat 'inf' as actual infinity

    # Otherwise treat as a variable name
    if token_str not in symbol_table:
        symbol_table[token_str] = sympy.Symbol(token_str, real=True)
    return symbol_table[token_str]


def parse_boolean_expression(expr_str, variables_of_interest=None, treat_inf_as_symbol=True):
    """
    Parse a string with C-style logical operators into a Sympy Boolean expression,
    then perform existential elimination of any variables NOT in variables_of_interest.
    Finally simplify the resulting expression.

    For example:
        (amount <= 6 && expense <= 1000) || (amount >= 7 && expense >= 1500)

    If variables_of_interest = ["amount"], then the final expression
    becomes (amount <= 6) || (amount >= 7), because the "expense" constraints
    are not contradictory, so expense is effectively a "don't care" variable.

    :param expr_str: The Boolean expression as a string.
    :param variables_of_interest: list of variable names to keep; all others become "don't care".
    :param treat_inf_as_symbol: if True, treat 'inf' as a symbolic variable named 'inf'.
                                if False, treat 'inf' as +∞ via sympy.oo.
    :return: a simplified Sympy Boolean expression in terms of variables_of_interest (DNF).
    """
    # 1) Parse the input into a disjunction (OR) of conjunctions (AND).
    #    We'll store it as a list of lists of Sympy relational objects:
    #    top_level = [ [rel1, rel2, ...], [rel3, rel4, ...], ... ]
    symbol_table = {}
    top_level = _parse_as_disjunction_of_conjunctions(expr_str, symbol_table, treat_inf_as_symbol)

    if variables_of_interest is None:
        variables_of_interest = []  # if None, interpret as empty

    # 2) For each conjunction, separate constraints by variable. If any
    #    "don't care" variable is contradictory => the conjunction is unsatisfiable.
    #    Otherwise, drop those constraints entirely (since we only need an existence).
    new_disjunction = []
    for conj_constraints in top_level:
        # conj_constraints is a list of Sympy relational expressions
        # group them by the variable(s) they mention
        grouping = {}  # var -> list of constraints
        unsatisfiable = False

        for rel in conj_constraints:
            # Example: rel could be (amount <= 6) or (expense > 1000)
            # Each is of type sympy.relational.Relational, e.g. Le(amount, 6).
            vars_in_rel = list(rel.free_symbols)
            if len(vars_in_rel) == 0:
                # Something like (True) or numeric? Then it either always holds or never.
                # We'll assume these are degenerate. Usually doesn't happen in typical usage.
                pass
            elif len(vars_in_rel) == 1:
                var = vars_in_rel[0]
                grouping.setdefault(var, []).append(rel)
            else:
                # This code handles only single-variable constraints.
                # If you have cross-variable constraints (like x + y <= 5),
                # you need a more advanced approach (quantifier elimination).
                raise ValueError(
                    f"Cannot handle cross-variable constraint: {rel}. "
                    "Only single-variable comparisons are supported."
                )

        # Now check each variable group
        # If variable.name not in variables_of_interest => treat it as "don't care"
        # => we only need to check that constraints on that variable are not contradictory
        # If contradictory => conj is unsatisfiable => we skip it
        # If satisfiable => we effectively remove them from the conjunction
        # If variable is in variables_of_interest => we keep them as is
        conj_kept_constraints = []
        for var, rel_list in grouping.items():
            if var.name in variables_of_interest:
                # Keep them
                conj_kept_constraints.extend(rel_list)
            else:
                # "don't care" variable => check satisfiability
                # We only have single-variable inequalities, so let's unify them
                if not _is_satisfiable_1d(rel_list, var):
                    unsatisfiable = True
                    break
                # else satisfiable => remove them
        if not unsatisfiable:
            new_disjunction.append(conj_kept_constraints)

    # 3) Convert new_disjunction (list of list of constraints) back to a single Sympy expression
    #    in OR-of-AND form, then simplify.
    if not new_disjunction:
        # No clauses survived => expression is unsatisfiable => return False
        return sympy.false

    # Build the Sympy expression
    or_expr = None
    for conj_list in new_disjunction:
        if conj_list:
            and_part = And(*conj_list) if len(conj_list) > 1 else conj_list[0]
        else:
            # If no constraints remain in the conjunction, that means it's "always True"
            # for the variables_of_interest. So that clause is True.
            and_part = sympy.true

        or_expr = and_part if or_expr is None else Or(or_expr, and_part)

    # 4) Simplify the final expression
    from sympy.logic.boolalg import simplify_logic
    simplified_expr = simplify_logic(or_expr, force=True, form='dnf')
    return simplified_expr


# -------------------------------------------------------------------
#   Parsing Helpers
# -------------------------------------------------------------------

def _parse_as_disjunction_of_conjunctions(expr_str, symbol_table, treat_inf_as_symbol):
    """
    Parse the input string into a list of lists of Sympy relational constraints.
    Outer list => disjunction (OR), each element => conjunction (AND).
    """
    # Replace && -> &, || -> |
    cleaned_expr = expr_str.replace('&&', '&').replace('||', '|')

    # Split by top-level OR
    or_clauses = _split_top_level(cleaned_expr, sep='|')

    top_level = []
    for or_clause in or_clauses:
        clause_str = or_clause.strip()
        # remove surrounding parentheses if present
        if clause_str.startswith('(') and clause_str.endswith(')'):
            clause_str = clause_str[1:-1].strip()

        # Now split by top-level &
        and_parts = _split_top_level(clause_str, sep='&')
        conj_list = []
        for part in and_parts:
            comp_str = part.strip()
            rel_expr = parse_comparison(comp_str, symbol_table, treat_inf_as_symbol)
            conj_list.append(rel_expr)
        top_level.append(conj_list)

    return top_level


def _split_top_level(expr_str, sep='|'):
    """
    Split `expr_str` by the top-level occurrences of `sep`.
    We keep track of parentheses depth to avoid splitting inside parentheses.

    E.g. '(a & b) | (c & d)' -> ['(a & b)', '(c & d)'] when sep='|'.
    """
    results = []
    bracket_level = 0
    current = []
    i = 0
    while i < len(expr_str):
        ch = expr_str[i]
        if ch == '(':
            bracket_level += 1
            current.append(ch)
        elif ch == ')':
            bracket_level -= 1
            current.append(ch)
        elif bracket_level == 0 and expr_str[i:i + len(sep)] == sep:
            results.append("".join(current).strip())
            current = []
            i += len(sep)
            continue
        else:
            current.append(ch)
        i += 1

    if current:
        results.append("".join(current).strip())
    return results


# -------------------------------------------------------------------
#   Single-Variable Satisfiability
# -------------------------------------------------------------------

def _is_satisfiable_1d(rel_list, var):
    """
    Given a list of single-variable (var) constraints like [var <= 6, var >= 3],
    check if there's at least one real value of `var` that satisfies them all.

    Because we only have linear inequalities/equalities of one variable in each rel,
    we can unify them by computing an intersection of intervals or sets.
    """
    # We'll track the intersection of constraints in interval form:
    # lower_bound, upper_bound, plus any == constraints.
    # If there's an equality constraint, that will drastically narrow the range.

    # We'll store them as numeric bounds: lower_bound = -∞ initially, upper_bound = +∞ initially
    # eq_value = None if no equality constraint, otherwise the specific value
    # We only handle strict and non-strict inequalities plus equality to a constant.

    import math

    lower_bound = -math.inf
    lower_strict = False  # track if it's '>' or '>='
    upper_bound = math.inf
    upper_strict = False
    eq_value = None  # if we ever get var == c

    for constraint in rel_list:
        # constraint is something like var <= 6
        if not isinstance(constraint, sympy.Rel):
            # unexpected
            return False
        # We'll check the type
        # E.g. constraint.rel_op in ['<','<=','>','>=','==']
        # and constraint.lhs, constraint.rhs
        lhs, rhs, op = constraint.lhs, constraint.rhs, constraint.rel_op

        # figure out if lhs is the variable or rhs is the variable
        # We assume 'var' is always on the left or right, and the other side is a number
        if lhs == var and rhs.is_number:
            val = rhs.evalf()
            if op == '<':
                upper_bound = min(upper_bound, val)
                # strictly less
                if val == upper_bound:
                    upper_strict = True
            elif op == '<=':
                upper_bound = min(upper_bound, val)
            elif op == '>':
                lower_bound = max(lower_bound, val)
                if val == lower_bound:
                    lower_strict = True
            elif op == '>=':
                lower_bound = max(lower_bound, val)
            elif op == '==':
                eq_value = val
            else:
                return False  # unknown op
        elif rhs == var and lhs.is_number:
            val = lhs.evalf()
            # now the operation is reversed
            # e.g. 6 >= var => var <= 6
            # We can unify by rewriting them in a standard form
            if op == '<':
                # means lhs < rhs => val < var => var > val
                lower_bound = max(lower_bound, val)
                if val == lower_bound:
                    lower_strict = True
            elif op == '<=':
                # val <= var => var >= val
                lower_bound = max(lower_bound, val)
            elif op == '>':
                # val > var => var < val
                upper_bound = min(upper_bound, val)
                if val == upper_bound:
                    upper_strict = True
            elif op == '>=':
                # val >= var => var <= val
                upper_bound = min(upper_bound, val)
            elif op == '==':
                # val == var
                eq_value = val
            else:
                return False
        else:
            # If the constraint doesn't have `var` on exactly one side,
            # it's more complex or doesn't match our assumption of single-variable linear constraint
            return False

    # Now check for contradiction:
    # 1) If eq_value is not None, we must ensure that eq_value is within [lower_bound, upper_bound].
    if eq_value is not None:
        # If eq_value < lower_bound or eq_value > upper_bound => contradiction
        # If eq_value == lower_bound but lower_strict => contradiction
        # If eq_value == upper_bound but upper_strict => contradiction
        if eq_value < lower_bound or eq_value > upper_bound:
            return False
        if eq_value == lower_bound and lower_strict:
            return False
        if eq_value == upper_bound and upper_strict:
            return False
        # Otherwise it's satisfied
        return True

    # 2) No eq_value => we must ensure lower_bound < upper_bound if strict bounds conflict
    # If lower_bound > upper_bound => contradiction
    if lower_bound > upper_bound:
        return False
    # If lower_bound == upper_bound but at least one bound is strict => contradiction
    if lower_bound == upper_bound and (lower_strict or upper_strict):
        return False

    # If we get here, there's some open or closed interval where var can lie
    return True


# -------------------------------------------------------------------
#   Demo
# -------------------------------------------------------------------
if __name__ == "__main__":
    expr_input = (
        "(amount <= 6 && expense <= 1000) || (amount >= 7 && expense >= 1500) || (amount >= 8 && expense >= 1500)"
    )
    vars_of_interest = ["amount"]

    simplified_expr = parse_boolean_expression(
        expr_input,
        variables_of_interest=vars_of_interest
    )

    print("Original expression:")
    print(expr_input)
    print("\nSimplified expression in DNF:")
    print(simplified_expr)
