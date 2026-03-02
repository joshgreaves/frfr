//! Container type validators: list, dict, tuple, set, frozenset.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFrozenSet, PyList, PySet, PyString, PyTuple};

use crate::compiled::CompiledValidator;
use crate::errors::union_error;

/// Validate list[T] - accepts list or tuple, validates elements.
pub fn validate_list(
    py: Python<'_>,
    target: PyObject,
    elem_validator: &CompiledValidator,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    // Accept list directly
    if let Ok(list) = data.downcast::<PyList>() {
        let validated: Vec<PyObject> = list
            .iter()
            .map(|item| elem_validator.validate(py, &item))
            .collect::<PyResult<Vec<_>>>()?;
        return Ok(PyList::new_bound(py, validated).into_any().unbind());
    }

    // Accept tuple, convert to list
    if let Ok(tuple) = data.downcast::<PyTuple>() {
        let validated: Vec<PyObject> = tuple
            .iter()
            .map(|item| elem_validator.validate(py, &item))
            .collect::<PyResult<Vec<_>>>()?;
        return Ok(PyList::new_bound(py, validated).into_any().unbind());
    }

    Err(union_error(py, target, data))
}

/// Validate untyped list - accepts list or tuple, no element validation.
pub fn validate_list_untyped(
    py: Python<'_>,
    target: PyObject,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    if let Ok(list) = data.downcast::<PyList>() {
        // Return a shallow copy
        let items: Vec<PyObject> = list.iter().map(|item| item.unbind()).collect();
        return Ok(PyList::new_bound(py, items).into_any().unbind());
    }

    if let Ok(tuple) = data.downcast::<PyTuple>() {
        let items: Vec<PyObject> = tuple.iter().map(|item| item.unbind()).collect();
        return Ok(PyList::new_bound(py, items).into_any().unbind());
    }

    Err(union_error(py, target, data))
}

/// Validate dict[str, V] - optimized for string keys.
pub fn validate_dict_str_key(
    py: Python<'_>,
    target: PyObject,
    val_validator: &CompiledValidator,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let dict = data
        .downcast::<PyDict>()
        .map_err(|_| union_error(py, target.clone(), data))?;

    let result = PyDict::new_bound(py);

    for (key, value) in dict.iter() {
        // Inline key validation - just check it's a string
        if !key.is_instance_of::<PyString>() {
            let builtins = py.import_bound("builtins")?;
            let str_type = builtins.getattr("str")?.unbind();
            return Err(union_error(py, str_type, &key));
        }

        let validated_value = val_validator.validate(py, &value)?;
        result.set_item(key, validated_value)?;
    }

    Ok(result.into_any().unbind())
}

/// Validate dict[K, V] - general case.
pub fn validate_dict(
    py: Python<'_>,
    target: PyObject,
    key_validator: &CompiledValidator,
    val_validator: &CompiledValidator,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let dict = data
        .downcast::<PyDict>()
        .map_err(|_| union_error(py, target, data))?;

    let result = PyDict::new_bound(py);

    for (key, value) in dict.iter() {
        let validated_key = key_validator.validate(py, &key)?;
        let validated_value = val_validator.validate(py, &value)?;
        result.set_item(validated_key, validated_value)?;
    }

    Ok(result.into_any().unbind())
}

/// Validate untyped dict.
pub fn validate_dict_untyped(
    py: Python<'_>,
    target: PyObject,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let dict = data
        .downcast::<PyDict>()
        .map_err(|_| union_error(py, target, data))?;

    // Return a shallow copy
    Ok(dict.copy()?.into_any().unbind())
}

/// Validate tuple[T, ...] - homogeneous tuple.
pub fn validate_tuple_homogeneous(
    py: Python<'_>,
    target: PyObject,
    elem_validator: &CompiledValidator,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    // Accept list or tuple
    let items: Vec<Bound<'_, PyAny>> = if let Ok(list) = data.downcast::<PyList>() {
        list.iter().collect()
    } else if let Ok(tuple) = data.downcast::<PyTuple>() {
        tuple.iter().collect()
    } else {
        return Err(union_error(py, target, data));
    };

    let validated: Vec<PyObject> = items
        .iter()
        .map(|item| elem_validator.validate(py, item))
        .collect::<PyResult<Vec<_>>>()?;

    Ok(PyTuple::new_bound(py, validated).into_any().unbind())
}

/// Validate tuple[T1, T2, ...] - fixed-length tuple.
pub fn validate_tuple_fixed(
    py: Python<'_>,
    target: PyObject,
    elem_validators: &[CompiledValidator],
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    // Accept list or tuple
    let items: Vec<Bound<'_, PyAny>> = if let Ok(list) = data.downcast::<PyList>() {
        list.iter().collect()
    } else if let Ok(tuple) = data.downcast::<PyTuple>() {
        tuple.iter().collect()
    } else {
        return Err(union_error(py, target.clone(), data));
    };

    // Check length
    if items.len() != elem_validators.len() {
        return Err(union_error(py, target, data));
    }

    let validated: Vec<PyObject> = items
        .iter()
        .zip(elem_validators.iter())
        .map(|(item, validator)| validator.validate(py, item))
        .collect::<PyResult<Vec<_>>>()?;

    Ok(PyTuple::new_bound(py, validated).into_any().unbind())
}

/// Validate untyped tuple.
pub fn validate_tuple_untyped(
    py: Python<'_>,
    target: PyObject,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    if let Ok(tuple) = data.downcast::<PyTuple>() {
        // Return as-is (tuples are immutable)
        return Ok(tuple.clone().into_any().unbind());
    }

    if let Ok(list) = data.downcast::<PyList>() {
        let items: Vec<PyObject> = list.iter().map(|item| item.unbind()).collect();
        return Ok(PyTuple::new_bound(py, items).into_any().unbind());
    }

    Err(union_error(py, target, data))
}

/// Validate set[T].
pub fn validate_set(
    py: Python<'_>,
    target: PyObject,
    elem_validator: &CompiledValidator,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    // Only accept set or frozenset - no coercion from list/tuple
    let items: Vec<Bound<'_, PyAny>> = if let Ok(set) = data.downcast::<PySet>() {
        set.iter().collect()
    } else if let Ok(frozenset) = data.downcast::<PyFrozenSet>() {
        frozenset.iter().collect()
    } else {
        return Err(union_error(py, target, data));
    };

    let result = PySet::empty_bound(py)?;
    for item in items {
        let validated = elem_validator.validate(py, &item)?;
        result.add(validated)?;
    }

    Ok(result.into_any().unbind())
}

/// Validate untyped set.
pub fn validate_set_untyped(
    py: Python<'_>,
    target: PyObject,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    if let Ok(set) = data.downcast::<PySet>() {
        // Create a copy
        let result = PySet::empty_bound(py)?;
        for item in set.iter() {
            result.add(item)?;
        }
        return Ok(result.into_any().unbind());
    }

    if let Ok(frozenset) = data.downcast::<PyFrozenSet>() {
        let result = PySet::empty_bound(py)?;
        for item in frozenset.iter() {
            result.add(item)?;
        }
        return Ok(result.into_any().unbind());
    }

    Err(union_error(py, target, data))
}

/// Validate frozenset[T].
pub fn validate_frozenset(
    py: Python<'_>,
    target: PyObject,
    elem_validator: &CompiledValidator,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    // Only accept set or frozenset
    let items: Vec<Bound<'_, PyAny>> = if let Ok(set) = data.downcast::<PySet>() {
        set.iter().collect()
    } else if let Ok(frozenset) = data.downcast::<PyFrozenSet>() {
        frozenset.iter().collect()
    } else {
        return Err(union_error(py, target, data));
    };

    let validated: Vec<PyObject> = items
        .iter()
        .map(|item| elem_validator.validate(py, item))
        .collect::<PyResult<Vec<_>>>()?;

    Ok(PyFrozenSet::new_bound(py, &validated)?.into_any().unbind())
}

/// Validate untyped frozenset.
pub fn validate_frozenset_untyped(
    py: Python<'_>,
    target: PyObject,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    if let Ok(frozenset) = data.downcast::<PyFrozenSet>() {
        return Ok(frozenset.clone().into_any().unbind());
    }

    if let Ok(set) = data.downcast::<PySet>() {
        let items: Vec<Bound<'_, PyAny>> = set.iter().collect();
        return Ok(PyFrozenSet::new_bound(py, &items)?.into_any().unbind());
    }

    Err(union_error(py, target, data))
}
