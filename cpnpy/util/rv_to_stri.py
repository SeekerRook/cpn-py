import numpy as np
from scipy.stats import norm, uniform, expon, lognorm, gamma

def random_variable_to_string(rv):
    """
    Given a pm4py RandomVariable (rv), produce a string that starts with '@+'
    followed by the appropriate Python function call using scipy.stats.

    Note: The returned string is a Python expression that you could
    theoretically evaluate to draw a sample, e.g. eval("@+norm.rvs(loc=0, scale=1)").
    You must ensure norm, uniform, etc. are in scope when evaluating.
    """
    dist_type = rv.get_distribution_type()
    params_str = rv.get_distribution_parameters()

    # Handle uninitialized or unknown distribution types
    if dist_type is None:
        return "@+0"  # Fallback to a constant 0

    if dist_type == "IMMEDIATE":
        # We interpret "IMMEDIATE" as a constant 0
        return "@+0"

    if dist_type == "DETERMINISTIC":
        # For a deterministic random variable, params_str is the constant value
        # Example: "5" -> "@+5"
        return f"@+{params_str}"

    if dist_type == "NORMAL":
        # For normal: params_str is something like "mu;sigma"
        mu_str, sigma_str = params_str.split(";")
        mu = float(mu_str)
        sigma = float(sigma_str)
        return f"@+norm.rvs(loc={mu}, scale={sigma})"

    if dist_type == "UNIFORM":
        # For uniform: params_str is something like "loc;scale"
        loc_str, scale_str = params_str.split(";")
        loc = float(loc_str)
        scale = float(scale_str)
        return f"@+uniform.rvs(loc={loc}, scale={scale})"

    if dist_type == "EXPONENTIAL":
        # For exponential: params_str is the rate (lambda), but in scipy:
        # scale = 1.0 / rate
        rate_str = params_str
        rate = float(rate_str)
        # We fix loc = 0.0 for typical exponential usage
        return f"@+expon.rvs(loc=0.0, scale={1.0 / rate})"

    if dist_type == "LOGNORMAL":
        # For lognormal: params_str is "s;loc;scale"
        s_str, loc_str, scale_str = params_str.split(";")
        s = float(s_str)
        loc = float(loc_str)
        scale = float(scale_str)
        return f"@+lognorm.rvs(s={s}, loc={loc}, scale={scale})"

    if dist_type == "GAMMA":
        # For gamma: params_str is "a;loc;scale"
        a_str, loc_str, scale_str = params_str.split(";")
        a = float(a_str)
        loc = float(loc_str)
        scale = float(scale_str)
        return f"@+gamma.rvs(a={a}, loc={loc}, scale={scale})"

    # Fallback for unknown types
    return "@+0"


def transform_transition_dict(transition_dict):
    """
    Transforms a dictionary {transition: RandomVariable} into
    {transition: '@+something'}, where 'something' is a valid Python expression
    to sample from that distribution using scipy.stats.

    Parameters
    ----------
    transition_dict : dict
        A dictionary mapping transitions (keys) to pm4py RandomVariable objects (values)

    Returns
    -------
    dict
        A dictionary mapping transitions to strings of the form '@+<PY_EXPRESSION>'
    """
    new_dict = {}
    for transition, rv in transition_dict.items():
        new_dict[transition] = random_variable_to_string(rv)
    return new_dict
