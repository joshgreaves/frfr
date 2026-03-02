//! Primitive type validators: int, float, str, bool, None, Any.

use pyo3::prelude::*;
use pyo3::types::{PyBool, PyFloat, PyInt, PyString};

use crate::errors::primitive_error;

/// Validate that data is an int (not a bool).
#[inline(always)]
pub fn validate_int(py: Python<'_>, data: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    // Reject bool explicitly - even though bool is a subclass of int
    if data.is_instance_of::<PyBool>() {
        return Err(primitive_error(py, "int", data));
    }

    if data.is_instance_of::<PyInt>() {
        return Ok(data.clone().unbind());
    }

    Err(primitive_error(py, "int", data))
}

/// Validate that data is a float, or coerce from int.
#[inline(always)]
pub fn validate_float(py: Python<'_>, data: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    // Reject bool explicitly
    if data.is_instance_of::<PyBool>() {
        return Err(primitive_error(py, "float", data));
    }

    // Accept float directly
    if data.is_instance_of::<PyFloat>() {
        return Ok(data.clone().unbind());
    }

    // Coerce int to float (lossless widening)
    if data.is_instance_of::<PyInt>() {
        let val: i64 = data.extract()?;
        return Ok(PyFloat::new_bound(py, val as f64).into_any().unbind());
    }

    Err(primitive_error(py, "float", data))
}

/// Validate that data is a str.
#[inline(always)]
pub fn validate_str(py: Python<'_>, data: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    if data.is_instance_of::<PyString>() {
        return Ok(data.clone().unbind());
    }

    Err(primitive_error(py, "str", data))
}

/// Validate that data is a bool.
#[inline(always)]
pub fn validate_bool(py: Python<'_>, data: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    if data.is_instance_of::<PyBool>() {
        return Ok(data.clone().unbind());
    }

    Err(primitive_error(py, "bool", data))
}

/// Validate that data is None.
#[inline(always)]
pub fn validate_none(py: Python<'_>, data: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    if data.is_none() {
        return Ok(py.None());
    }

    Err(primitive_error(py, "NoneType", data))
}

/// Accept any data without validation.
#[inline(always)]
pub fn validate_any(_py: Python<'_>, data: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    Ok(data.clone().unbind())
}
