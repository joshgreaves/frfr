//! Structured type validators: TypedDict, dataclass, NamedTuple.

use std::collections::HashSet;

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyString, PyTuple};

use crate::compiled::CompiledValidator;
use crate::errors::{error_with_path, union_error};

/// Info for TypedDict validation.
#[derive(Clone)]
pub struct TypedDictInfo {
    pub target: PyObject,
    pub fields: Vec<(String, CompiledValidator)>,
    pub required_keys: HashSet<String>,
    pub all_field_names: HashSet<String>,
}

/// Info for dataclass validation.
#[derive(Clone)]
pub struct DataclassInfo {
    pub target: PyObject,
    pub fields: Vec<(String, CompiledValidator)>,
    pub required_fields: HashSet<String>,
    pub num_fields: usize,
}

/// Info for NamedTuple validation.
#[derive(Clone)]
pub struct NamedTupleInfo {
    pub target: PyObject,
    pub fields: Vec<(String, CompiledValidator)>,
    pub required_fields: HashSet<String>,
    pub all_field_names: HashSet<String>,
}

/// Validate TypedDict.
pub fn validate_typed_dict(
    py: Python<'_>,
    info: &TypedDictInfo,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    // Must be a dict
    let dict = data
        .downcast::<PyDict>()
        .map_err(|_| union_error(py, info.target.clone(), data))?;

    // Quick length check for unexpected keys
    let dict_len = dict.len();
    let num_fields = info.all_field_names.len();
    if dict_len > num_fields {
        for key in dict.keys() {
            if !key.is_instance_of::<PyString>() {
                return Err(error_with_path(info.target.clone(), data, "keys must be strings"));
            }
            let key_str: &str = key.extract()?;
            if !info.all_field_names.contains(key_str) {
                return Err(error_with_path(
                    info.target.clone(),
                    data,
                    &format!("unexpected key: {}", key_str),
                ));
            }
        }
    }

    // Build result dict in single pass
    let result = PyDict::new_bound(py);
    let mut found_count = 0usize;

    for (field_name, validator) in &info.fields {
        if let Some(value) = dict.get_item(field_name)? {
            let validated = validator.validate(py, &value)?;
            result.set_item(field_name.as_str(), validated)?;
            found_count += 1;
        } else if info.required_keys.contains(field_name) {
            return Err(error_with_path(
                info.target.clone(),
                data,
                &format!("missing key: {}", field_name),
            ));
        }
    }

    // Check for unexpected keys if we didn't find all dict keys
    if found_count < dict_len {
        for key in dict.keys() {
            if !key.is_instance_of::<PyString>() {
                return Err(error_with_path(info.target.clone(), data, "keys must be strings"));
            }
            let key_str: &str = key.extract()?;
            if !info.all_field_names.contains(key_str) {
                return Err(error_with_path(
                    info.target.clone(),
                    data,
                    &format!("unexpected key: {}", key_str),
                ));
            }
        }
    }

    Ok(result.into_any().unbind())
}

/// Validate dataclass.
pub fn validate_dataclass(
    py: Python<'_>,
    info: &DataclassInfo,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    // Must be a dict
    let dict = data
        .downcast::<PyDict>()
        .map_err(|_| union_error(py, info.target.clone(), data))?;

    // Quick length check: if too many keys, there must be unexpected ones
    let dict_len = dict.len();
    if dict_len > info.num_fields {
        // Find the unexpected key for error message (error path only)
        for key in dict.keys() {
            let key_str: &str = key.extract()?;
            let mut found = false;
            for (field_name, _) in &info.fields {
                if field_name == key_str {
                    found = true;
                    break;
                }
            }
            if !found {
                return Err(error_with_path(
                    info.target.clone(),
                    data,
                    &format!("unexpected key: {}", key_str),
                ));
            }
        }
    }

    // Build positional args in field order, checking required fields
    let mut args: Vec<PyObject> = Vec::with_capacity(info.fields.len());
    let mut found_count = 0usize;
    let mut has_missing_optional = false;

    for (field_name, validator) in &info.fields {
        if let Some(value) = dict.get_item(field_name)? {
            let validated = validator.validate(py, &value)?;
            args.push(validated);
            found_count += 1;
        } else if info.required_fields.contains(field_name) {
            return Err(error_with_path(
                info.target.clone(),
                data,
                &format!("missing field: {}", field_name),
            ));
        } else {
            // Optional field not provided - need kwargs path
            has_missing_optional = true;
            break;
        }
    }

    // If we found fewer fields than dict has, there are unexpected keys
    if found_count < dict_len {
        for key in dict.keys() {
            let key_str: &str = key.extract()?;
            let mut found = false;
            for (field_name, _) in &info.fields {
                if field_name == key_str {
                    found = true;
                    break;
                }
            }
            if !found {
                return Err(error_with_path(
                    info.target.clone(),
                    data,
                    &format!("unexpected key: {}", key_str),
                ));
            }
        }
    }

    // Fast path: all fields provided, use positional args
    if !has_missing_optional {
        let args_tuple = PyTuple::new_bound(py, args);
        return Ok(info.target.bind(py).call1(args_tuple)?.unbind());
    }

    // Slow path: some optional fields missing, use kwargs
    let kwargs = PyDict::new_bound(py);
    for (field_name, validator) in &info.fields {
        if let Some(value) = dict.get_item(field_name)? {
            let validated = validator.validate(py, &value)?;
            kwargs.set_item(field_name.as_str(), validated)?;
        }
    }
    Ok(info.target.bind(py).call((), Some(&kwargs))?.unbind())
}

/// Validate NamedTuple from dict input.
pub fn validate_namedtuple_from_dict(
    py: Python<'_>,
    info: &NamedTupleInfo,
    dict: &Bound<'_, PyDict>,
) -> PyResult<PyObject> {
    // Quick length check for unexpected keys
    let dict_len = dict.len();
    let num_fields = info.all_field_names.len();
    if dict_len > num_fields {
        for key in dict.keys() {
            let key_str: &str = key.extract()?;
            if !info.all_field_names.contains(key_str) {
                return Err(error_with_path(
                    info.target.clone(),
                    dict.as_any(),
                    &format!("unexpected key: {}", key_str),
                ));
            }
        }
    }

    // Build kwargs in single pass
    let kwargs = PyDict::new_bound(py);
    let mut found_count = 0usize;

    for (field_name, validator) in &info.fields {
        if let Some(value) = dict.get_item(field_name)? {
            let validated = validator.validate(py, &value)?;
            kwargs.set_item(field_name.as_str(), validated)?;
            found_count += 1;
        } else if info.required_fields.contains(field_name) {
            return Err(error_with_path(
                info.target.clone(),
                dict.as_any(),
                &format!("missing field: {}", field_name),
            ));
        }
    }

    // Check for unexpected keys if we didn't find all dict keys
    if found_count < dict_len {
        for key in dict.keys() {
            let key_str: &str = key.extract()?;
            if !info.all_field_names.contains(key_str) {
                return Err(error_with_path(
                    info.target.clone(),
                    dict.as_any(),
                    &format!("unexpected key: {}", key_str),
                ));
            }
        }
    }

    // Call the NamedTuple constructor with kwargs
    Ok(info.target.bind(py).call((), Some(&kwargs))?.unbind())
}

/// Validate NamedTuple from list/tuple input.
pub fn validate_namedtuple_from_sequence(
    py: Python<'_>,
    info: &NamedTupleInfo,
    items: Vec<Bound<'_, PyAny>>,
) -> PyResult<PyObject> {
    // Check length matches
    if items.len() != info.fields.len() {
        return Err(union_error(py, info.target.clone(), &PyTuple::new_bound(py, &items).into_any()));
    }

    // Validate each item
    let validated: Vec<PyObject> = items
        .iter()
        .zip(info.fields.iter())
        .map(|(item, (_, validator))| validator.validate(py, item))
        .collect::<PyResult<Vec<_>>>()?;

    // Call constructor with positional args
    let args = PyTuple::new_bound(py, validated);
    Ok(info.target.bind(py).call1(args)?.unbind())
}

/// Validate NamedTuple (accepts dict, list, or tuple).
pub fn validate_namedtuple(
    py: Python<'_>,
    info: &NamedTupleInfo,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    // Try dict first
    if let Ok(dict) = data.downcast::<PyDict>() {
        return validate_namedtuple_from_dict(py, info, dict);
    }

    // Try list
    if let Ok(list) = data.downcast::<PyList>() {
        let items: Vec<Bound<'_, PyAny>> = list.iter().collect();
        return validate_namedtuple_from_sequence(py, info, items);
    }

    // Try tuple
    if let Ok(tuple) = data.downcast::<PyTuple>() {
        let items: Vec<Bound<'_, PyAny>> = tuple.iter().collect();
        return validate_namedtuple_from_sequence(py, info, items);
    }

    Err(union_error(py, info.target.clone(), data))
}
