//! Union type validators.

use pyo3::prelude::*;
use pyo3::types::{PyBool, PyFloat, PyInt, PyString};

use crate::compiled::CompiledValidator;
use crate::errors::union_error;

/// Info for optimized primitive union validation.
#[derive(Clone, Debug)]
pub struct PrimitiveUnionInfo {
    pub has_int: bool,
    pub has_float: bool,
    pub has_str: bool,
    pub has_bool: bool,
    pub has_none: bool,
    pub float_before_int: bool,
}

impl PrimitiveUnionInfo {
    pub fn new(
        has_int: bool,
        has_float: bool,
        has_str: bool,
        has_bool: bool,
        has_none: bool,
        float_before_int: bool,
    ) -> Self {
        PrimitiveUnionInfo {
            has_int,
            has_float,
            has_str,
            has_bool,
            has_none,
            float_before_int,
        }
    }
}

/// Validate a primitive union (int, float, str, bool, None only).
/// This is highly optimized with inline type checks - no function calls.
#[inline(always)]
pub fn validate_primitive_union(
    py: Python<'_>,
    target: PyObject,
    info: &PrimitiveUnionInfo,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    // Bool check first (before int, since bool is int subclass)
    if data.is_instance_of::<PyBool>() {
        if info.has_bool {
            return Ok(data.clone().unbind());
        }
        return Err(union_error(py, target, data));
    }

    // Int check
    if data.is_instance_of::<PyInt>() {
        if info.float_before_int {
            // Coerce int to float if float comes before int in union
            let val: i64 = data.extract()?;
            return Ok(PyFloat::new_bound(py, val as f64).into_any().unbind());
        }
        if info.has_int {
            return Ok(data.clone().unbind());
        }
        if info.has_float {
            // Coerce int to float
            let val: i64 = data.extract()?;
            return Ok(PyFloat::new_bound(py, val as f64).into_any().unbind());
        }
        return Err(union_error(py, target, data));
    }

    // Float check
    if data.is_instance_of::<PyFloat>() {
        if info.has_float {
            return Ok(data.clone().unbind());
        }
        return Err(union_error(py, target, data));
    }

    // String check
    if data.is_instance_of::<PyString>() {
        if info.has_str {
            return Ok(data.clone().unbind());
        }
        return Err(union_error(py, target, data));
    }

    // None check
    if data.is_none() {
        if info.has_none {
            return Ok(py.None());
        }
    }

    Err(union_error(py, target, data))
}

/// Validate Optional[T] (T | None).
#[inline(always)]
pub fn validate_optional(
    py: Python<'_>,
    inner_validator: &CompiledValidator,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    if data.is_none() {
        return Ok(py.None());
    }
    inner_validator.validate(py, data)
}

/// Validate a 2-type union (optimized to avoid loop).
pub fn validate_union_2(
    py: Python<'_>,
    target: PyObject,
    v0: &CompiledValidator,
    v1: &CompiledValidator,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    // Try first type
    if let Ok(result) = v0.validate(py, data) {
        return Ok(result);
    }

    // Try second type
    if let Ok(result) = v1.validate(py, data) {
        return Ok(result);
    }

    Err(union_error(py, target, data))
}

/// Validate a general union type.
pub fn validate_union(
    py: Python<'_>,
    target: PyObject,
    validators: &[CompiledValidator],
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    for validator in validators {
        if let Ok(result) = validator.validate(py, data) {
            return Ok(result);
        }
    }

    Err(union_error(py, target, data))
}
