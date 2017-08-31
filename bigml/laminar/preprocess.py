import collections

from copy import deepcopy

from bigml.laminar.constants import NUMERIC, CATEGORICAL

MODE_CONCENTRATION = 0.1
MODE_STRENGTH = 3

MEAN = "mean"
STANDARD_DEVIATION = "stdev"

ZERO = "zero_value"
ONE = "one_value"


def dtype_ok(dtype_fn):
    return dtype_fn is not None and dtype_fn in [int, float]


def np_zeros(x_dim, y_dim, dtype_fn=None):
    value = "0"
    try:
        if dtype_ok(dtype_fn):
            value = dtype_fn(value)
    except ValueError:
        pass
    array = []
    for i in range(x_dim):
        array[i] = []
        for j in range(y_dim):
            array[i].append(value)
    return array


def np_asarray(array, dtype_fn=None):
    new_array = deepcopy(array)
    if not isinstance(array, list):
        new_array = [item for item in new_array]
    try:
        if dtype_ok(dtype_fn):
            new_array = [dtype_fn(item) for item in new_array]
    except (ValueError, NameError):
        pass
    return new_array


def np_c_(array_a, array_c):
    if array_a in [None, []]:
        return [array_c]

    new_array = deepcopy(array_a)
    for i, item_c in enumerate(array_c):
        new_array[i].append(item_c)

    return new_array


def index(alist, value):
    try:
        return alist.index(value)
    except ValueError:
        return None

def one_hot(vector, possible_values):
    idxs = list(enumerate(index(possible_values, v) for v in vector))
    valid_pairs = filter(lambda x: x[1] is not None, idxs)
    outvec = np_zeros((len(idxs), len(possible_values)), dtype_fn=float)
    outvec[[v[0] for v in valid_pairs], [v[1] for v in valid_pairs]] = 1

    return outvec

def standardize(vector, mn, stdev):
    newvec = [component - mn for component in vector]

    if stdev > 0:
        newvec = [component / stdev for component in newvec]

    return newvec

def binarize(vector, zero, one):
    if one == 0.0:
        vector[vector == one] = 1.0
        vector[(vector != one) & (vector != 1.0)] = 0.0
    else:
        vector[vector != one] = 0.0
        vector[vector == one] = 1.0

    return vector

def moments(amap):
    return amap[MEAN], amap[STANDARD_DEVIATION]

def bounds(amap):
    return amap[ZERO], amap[ONE]

def transform(vector, spec):
    vtype = spec['type']

    if vtype == NUMERIC:
        if STANDARD_DEVIATION in spec:
            mn, stdev = moments(spec)
            output = standardize(vector, mn, stdev)
        elif ZERO in spec:
            low, high = bounds(spec)
            output = binarize(vector, low, high)
        else:
            raise ValueError("'%s' is not a valid numeric spec!" % str(spec))
    elif vtype == CATEGORICAL:
        output = one_hot(vector, spec['values'])
    else:
        raise ValueError("'%s' is not a valid spec type!" % vtype)
    return output


def preprocess(columns, specs):
    outdata = None

    for spec in specs:
        column = columns[spec['index']]

        if spec['type'] == NUMERIC:
            column = np_asarray(column, dtype_fn=float)

        outarray = transform(column, spec)

        if outdata is not None:
            outdata = np_c_(outdata, outarray)
        else:
            outdata = [outarray]

    return outdata
