import numpy as np

_bit_depth_mult_offset = {8:  (254, 127),
                          12: (4094, 2047),
                          14: (16382, 8191),
                          16: (65534, 32767)}


def create_prefix(data):
    return "#"+str(len(list(str(len(data)))))+str(len(data))

def bifloat_to_uint(value, bit_depth):
    """Convert a float on the range [-1.0, 1.0] to a unsigned int.

    Not a totally straightforward conversion, this conversion will result in matching
    values seen on the AWG, however perfect decimals may not be perfect as certain
    fractions are not perfectly representable in binary.

    Args:
        value: a single float, or list of floats, or numpy array of
            floats to operate on
        bit_depth: the target AWG's bit depth, taken from the set {8, 12, 14, 16}

    Returns:
        the converted input value/list/ndarray

    Raises:
        ValueError for a bit depth outside the set of supported values.
    """
    try:
        mult, offset = _bit_depth_mult_offset[bit_depth]
    except KeyError:
        raise ValueError("No rule exists for converting a bipolar float to a bit depth of "
                         "'{}'; supported bit depths are {}."
                         .format(bit_depth, _bit_depth_mult_offset.keys()))
    # ndarray case
    if isinstance(value, np.ndarray):
        output = np.empty(value.shape, dtype=int)
        np.multiply(value, mult, output, casting='unsafe')
        output += offset
        return output

    # generic iterable case
    try:
        val_iter = iter(value)
        return [int(val*mult + offset) for val in val_iter]
    except TypeError:
        # hopefully this is a scalar
        return int(value * mult + offset)

def uint_to_bifloat(value, bit_depth):
    """Convert an unsigned int to a float on the range [-1.0, 1.0].

    This is an undo of the bifloat_to_uint function.

    Args:
        value: a single uint, or list of uints, or numpy array of
            uints to operate on
        bit_depth: the target AWG's bit depth, taken from the set {8, 12, 14, 16}

    Returns:
        the converted input value/list/ndarray

    Raises:
        ValueError for a bit depth outside the set of supported values.
    """
    try:
        mult, offset = _bit_depth_mult_offset[bit_depth]
    except KeyError:
        raise ValueError("No rule exists for converting a bipolar float to a bit depth of "
                         "'{}'; supported bit depths are {}."
                         .format(bit_depth, _bit_depth_mult_offset.keys()))
    # ndarray case
    if isinstance(value, np.ndarray):
        output = np.empty(value.shape, dtype=float)
        value = value - float(offset)
        np.divide(value, float(mult), output, casting='unsafe')
        return output

    # generic iterable case
    try:
        val_iter = iter(value)
        return [float((val- offset)/float(mult)) for val in val_iter]
    except TypeError:
        # hopefully this is a scalar
        return float((value- offset)/float(mult))



def merge_arb_and_markers(arb=None, mk1=None, mk2=None, bit_depth=14):
    """Merge arbitrary waveform and marker values into a binary array of AWG codes.

    If any of the inputs are not supplied, they will be filled with placeholder
    arrays of zeros.  This function is only set up to support 10 and 12-bit AWGs

    Args:
        arb: the arbitrary waveform data on the range [-1.0, 1.0]
        mk1, mk2: the marker data.  Can be supplied as a booleans, integers
            (0 -> off, non-zero -> on), or floats (0.0 -> off, all other values -> on)

    Returns:
        An ndarray of Tektronix-formatted AWG sample codes.

    Raises:
        ValueError if no sequences were supplied or an unsupported bit depth was
            provided.
        UnequalPatternLengths if any of the input patterns were of unequal length.
    """
    supported_bit_depths = (8, 14)
    if bit_depth not in supported_bit_depths:
        raise ValueError("Unsupported bit depth of {}; valid bit depths are {}"
                         .format(bit_depth, supported_bit_depths))
    if arb is None and mk1 is None and mk2 is None:
        raise ValueError("Must supply at least one sequence pattern to create a"
                         " merged AWG binary array.")
    if arb is not None:
        master_pat = arb
    else:
        master_pat = mk1 if mk1 is not None else mk2

    seq_len = len(master_pat)

    arb = np.zeros(seq_len, dtype=float) if arb is None else arb
    mk1 = np.zeros(seq_len, dtype=bool) if mk1 is None else mk1.astype(bool)
    mk2 = np.zeros(seq_len, dtype=bool) if mk2 is None else mk2.astype(bool)

    if len(arb) != len(mk1) or len(mk1) != len(mk2):
        raise UnequalPatternLengths("Supplied patterns of unequal length: "
                                    "len(arb) = {}, len(mk1) = {}, len(mk2) = {}"
                                    .format(len(arb), len(mk1), len(mk2)))

    # all patterns have the same length and are valid
    # convert the bipolar float to integer
    arb = bifloat_to_uint(arb, bit_depth).astype("<u2", copy=False)
    #if bit_depth == 8:
    #    np.left_shift(arb, 6, arb)

    mk1 = mk1.astype("<u2", copy=False)
    mk2 = mk2.astype("<u2", copy=False)

    # bit shift mk1 and mk2 to the correct flag bits, 15 and 16 respectively
    np.left_shift(mk1, 14, mk1)
    np.left_shift(mk2, 15, mk2)
    print bin(arb[5])

    np.bitwise_or(arb, mk1, arb)
    np.bitwise_or(arb, mk2, arb)

    return arb

def ints_to_byte_str(codes):
    """Convert an ndarray of AWG sample codes to bytes of the proper endianness.

    Args:
        codes: ndarray of AWG sample codes

    Returns: a byte array in little-endian order.

    Raises:
        TypeError if the incoming ndarray object does not have meaningful
            endianess.
    """
    # get the endianness of the ndarray
    byte_order = codes.dtype.byteorder
    if byte_order == '=':
        # native byte order, ask the system
        byte_order = sys.byteorder
    elif byte_order == '<':
        byte_order = 'little'
    elif byte_order == '>':
        byte_order = 'big'
    else:
        raise TypeError("Got an ndarray object without meaningful endianness!")

    # if we're little-endian, return the bytes
    if byte_order == 'little':
        return codes.tobytes()
    else:
    # otherwise, byte-swap first
        return codes.byteswap().tobytes()
#.4943891
def byte_str_to_vals(codes,str_format="INT"):
    if str_format == "INT":
        vals_ints = np.fromstring(codes, dtype="<u2")
        (arb, mk1, mk2) = unmerge_arb_and_markers(vals_ints)
        return (uint_to_bifloat(arb, 14), mk1, mk2)
    elif str_format == "REAL":
        return np.fromstring(codes, dtype="<f4, <u1")

def unmerge_arb_and_markers(codes):
    seq_len = len(codes)

    arb_mask = np.zeros(seq_len, dtype="<u2")+2**14-1
    mk1_mask = np.zeros(seq_len, dtype="<u2")+2**14
    mk2_mask = np.zeros(seq_len, dtype="<u2")+2**15

    arb = np.empty(seq_len, dtype='uint16')
    mk1 = np.empty(seq_len, dtype=bool)

    mk2 = np.empty(seq_len, dtype=bool)

    np.bitwise_and(codes, arb_mask, arb)
    np.bitwise_and(codes, mk1_mask, mk1_mask)
    np.bitwise_and(codes, mk2_mask, mk2_mask)

    np.not_equal(mk1_mask, np.zeros(seq_len), mk1)
    np.not_equal(mk2_mask, np.zeros(seq_len), mk2)

    return (arb, mk1, mk2)

class UnequalPatternLengths(Exception):
    pass






