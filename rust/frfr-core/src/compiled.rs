//! Compiled validator enum - the core of the validation system.
//!
//! Each variant holds pre-computed information needed for validation,
//! eliminating the need for runtime type introspection.

use pyo3::prelude::*;

use crate::errors::union_error;
use crate::types::containers;
use crate::types::primitives;
use crate::types::unions::{self, PrimitiveUnionInfo};

/// A compiled validator that can validate data without type introspection.
#[derive(Clone)]
pub enum CompiledValidator {
    // Primitives
    Int,
    Float,
    Str,
    Bool,
    None,
    Any,

    // Containers
    List {
        target: PyObject,
        elem: Box<CompiledValidator>,
    },
    ListUntyped {
        target: PyObject,
    },
    Dict {
        target: PyObject,
        key: Box<CompiledValidator>,
        val: Box<CompiledValidator>,
    },
    DictStrKey {
        target: PyObject,
        val: Box<CompiledValidator>,
    },
    DictUntyped {
        target: PyObject,
    },
    Tuple {
        target: PyObject,
        elems: Vec<CompiledValidator>,
    },
    TupleHomogeneous {
        target: PyObject,
        elem: Box<CompiledValidator>,
    },
    TupleUntyped {
        target: PyObject,
    },
    Set {
        target: PyObject,
        elem: Box<CompiledValidator>,
    },
    SetUntyped {
        target: PyObject,
    },
    FrozenSet {
        target: PyObject,
        elem: Box<CompiledValidator>,
    },
    FrozenSetUntyped {
        target: PyObject,
    },

    // Union types
    Optional {
        inner: Box<CompiledValidator>,
    },
    PrimitiveUnion {
        target: PyObject,
        info: PrimitiveUnionInfo,
    },
    Union2 {
        target: PyObject,
        v0: Box<CompiledValidator>,
        v1: Box<CompiledValidator>,
    },
    Union {
        target: PyObject,
        validators: Vec<CompiledValidator>,
    },

    // Literal
    Literal {
        target: PyObject,
        allowed: Vec<PyObject>,
    },

    // Delegate to Python's compiled validator (for dataclass, TypedDict, NamedTuple)
    // This leverages Python's fast code generation for constructor calls
    PythonDelegate {
        validator: PyObject,
    },
}

impl CompiledValidator {
    /// Validate data against this compiled validator.
    pub fn validate(&self, py: Python<'_>, data: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        match self {
            // Primitives
            CompiledValidator::Int => primitives::validate_int(py, data),
            CompiledValidator::Float => primitives::validate_float(py, data),
            CompiledValidator::Str => primitives::validate_str(py, data),
            CompiledValidator::Bool => primitives::validate_bool(py, data),
            CompiledValidator::None => primitives::validate_none(py, data),
            CompiledValidator::Any => primitives::validate_any(py, data),

            // Containers
            CompiledValidator::List { target, elem } => {
                containers::validate_list(py, target.clone(), elem, data)
            }
            CompiledValidator::ListUntyped { target } => {
                containers::validate_list_untyped(py, target.clone(), data)
            }
            CompiledValidator::Dict { target, key, val } => {
                containers::validate_dict(py, target.clone(), key, val, data)
            }
            CompiledValidator::DictStrKey { target, val } => {
                containers::validate_dict_str_key(py, target.clone(), val, data)
            }
            CompiledValidator::DictUntyped { target } => {
                containers::validate_dict_untyped(py, target.clone(), data)
            }
            CompiledValidator::Tuple { target, elems } => {
                containers::validate_tuple_fixed(py, target.clone(), elems, data)
            }
            CompiledValidator::TupleHomogeneous { target, elem } => {
                containers::validate_tuple_homogeneous(py, target.clone(), elem, data)
            }
            CompiledValidator::TupleUntyped { target } => {
                containers::validate_tuple_untyped(py, target.clone(), data)
            }
            CompiledValidator::Set { target, elem } => {
                containers::validate_set(py, target.clone(), elem, data)
            }
            CompiledValidator::SetUntyped { target } => {
                containers::validate_set_untyped(py, target.clone(), data)
            }
            CompiledValidator::FrozenSet { target, elem } => {
                containers::validate_frozenset(py, target.clone(), elem, data)
            }
            CompiledValidator::FrozenSetUntyped { target } => {
                containers::validate_frozenset_untyped(py, target.clone(), data)
            }

            // Unions
            CompiledValidator::Optional { inner } => unions::validate_optional(py, inner, data),
            CompiledValidator::PrimitiveUnion { target, info } => {
                unions::validate_primitive_union(py, target.clone(), info, data)
            }
            CompiledValidator::Union2 { target, v0, v1 } => {
                unions::validate_union_2(py, target.clone(), v0, v1, data)
            }
            CompiledValidator::Union { target, validators } => {
                unions::validate_union(py, target.clone(), validators, data)
            }

            // Literal
            CompiledValidator::Literal { target, allowed } => {
                validate_literal(py, target.clone(), allowed, data)
            }

            // Delegate to Python's compiled validator
            CompiledValidator::PythonDelegate { validator } => {
                validator.call1(py, (data,))
            }
        }
    }
}

/// Validate Literal type.
fn validate_literal(
    py: Python<'_>,
    target: PyObject,
    allowed: &[PyObject],
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let data_type = data.get_type();

    for val in allowed {
        let val_bound = val.bind(py);
        // Check type and value match
        if data_type.is(&val_bound.get_type()) && data.eq(val_bound)? {
            return Ok(data.clone().unbind());
        }
    }

    Err(union_error(py, target, data))
}
