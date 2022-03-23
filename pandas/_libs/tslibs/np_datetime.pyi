import numpy as np

class OutOfBoundsDatetime(ValueError): ...

# only exposed for testing
def py_get_unit_from_dtype(dtype: np.dtype): ...
def astype_overflowsafe(
    arr: np.ndarray, dtype: np.dtype, copy: bool = ...
) -> np.ndarray: ...
