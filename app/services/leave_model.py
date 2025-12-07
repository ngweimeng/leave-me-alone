import xpress as xp


def solve_leave_lp(
    date_range, holidays, blocked_days, leave_available, adjacency_weight: float = 1.0, prebooked_days=None
):
    m = xp.problem()

    x = {d: xp.var(vartype=xp.binary) for d in date_range}  # leave days
    y = {d: xp.var(vartype=xp.binary) for d in date_range}  # break days

    # adjacency variables for consecutive break-days pairs (linearized AND)
    a = {}
    for i in range(len(date_range) - 1):
        a[date_range[i]] = xp.var(vartype=xp.binary)

    # register variables on the problem (add dictionaries separately)
    m.addVariable(x)
    m.addVariable(y)
    m.addVariable(a)

    # Cannot take leave on blocked days
    for d in blocked_days:
        if d in x:
            m.addConstraint(x[d] == 0)

    # Force prebooked days to be leave days (they count toward the leave budget)
    if prebooked_days:
        for d in prebooked_days:
            if d in x:
                m.addConstraint(x[d] == 1)

    # Leave budget
    m.addConstraint(xp.Sum(x[d] for d in date_range) <= leave_available)

    for d in date_range:
        is_free = d.weekday() >= 5 or d in holidays
        if is_free:
            m.addConstraint(y[d] == 1)
        else:
            m.addConstraint(y[d] <= x[d])

    # Link adjacency vars: a[d] == y[d] AND y[next]
    for i in range(len(date_range) - 1):
        d = date_range[i]
        dn = date_range[i + 1]
        # a[d] <= y[d]
        m.addConstraint(a[d] <= y[d])
        # a[d] <= y[dn]
        m.addConstraint(a[d] <= y[dn])
        # a[d] >= y[d] + y[dn] - 1
        m.addConstraint(a[d] >= y[d] + y[dn] - 1)

    # Objective: maximize total break days plus a bonus for consecutive days
    # (adjacency_weight controls how strongly we prefer contiguous runs).
    m.setObjective(
        xp.Sum(y[d] for d in date_range) + adjacency_weight * xp.Sum(a[d] for d in a),
        sense=xp.maximize,
    )

    m.solve()

    # Retrieve variable values via the problem instance (Xpress variables
    break_days = [d for d in date_range if m.getSolution(y[d]) > 0.5]
    leave_days = [d for d in date_range if m.getSolution(x[d]) > 0.5]

    return break_days, leave_days
