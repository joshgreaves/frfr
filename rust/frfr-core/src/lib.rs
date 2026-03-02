//! frfr-core: Rust implementation of frfr validation.
//!
//! This module provides high-performance type validation for Python,
//! matching the API of the pure-Python frfr library.

use std::collections::HashMap;
use std::sync::RwLock;

use pyo3::prelude::*;
use pyo3::types::PyTuple;

mod compiled;
mod errors;
mod types;

use compiled::CompiledValidator;
use errors::ValidationError;
use types::unions::PrimitiveUnionInfo;

/// Cache for compiled validators, keyed by type id.
type ValidatorCache = HashMap<usize, CompiledValidator>;

/// The main Validator class.
#[pyclass(module = "frfr._core")]
pub struct Validator {
    /// Cache of compiled validators.
    cache: RwLock<ValidatorCache>,
    /// Whether this validator is frozen (no new registrations allowed).
    #[pyo3(get)]
    frozen: bool,
}

#[pymethods]
impl Validator {
    #[new]
    #[pyo3(signature = (*, frozen = false))]
    pub fn new(frozen: bool) -> Self {
        Validator {
            cache: RwLock::new(HashMap::new()),
            frozen,
        }
    }

    /// Validate and coerce data to the given type.
    pub fn validate(
        &self,
        py: Python<'_>,
        target: &Bound<'_, PyAny>,
        data: &Bound<'_, PyAny>,
    ) -> PyResult<PyObject> {
        let validator = self.compile(py, target)?;
        validator.validate(py, data)
    }
}

impl Validator {
    /// Compile a type into a CompiledValidator.
    pub fn compile(&self, py: Python<'_>, target: &Bound<'_, PyAny>) -> PyResult<CompiledValidator> {
        let target_id = target.as_ptr() as usize;

        // Check cache first
        {
            let cache = self.cache.read().unwrap();
            if let Some(validator) = cache.get(&target_id) {
                return Ok(validator.clone());
            }
        }

        // Check if type contains structured types (dataclass, TypedDict, NamedTuple)
        // If so, delegate entirely to Python to avoid FFI overhead per item
        if self.contains_structured_type(py, target)? {
            let validator = self.build_python_delegate(py, target)?;
            let mut cache = self.cache.write().unwrap();
            cache.insert(target_id, validator.clone());
            return Ok(validator);
        }

        // Build the Rust validator
        let validator = self.build_validator(py, target)?;

        // Cache it
        {
            let mut cache = self.cache.write().unwrap();
            cache.insert(target_id, validator.clone());
        }

        Ok(validator)
    }

    /// Check if a type contains any structured types (dataclass, TypedDict, NamedTuple)
    fn contains_structured_type(&self, py: Python<'_>, target: &Bound<'_, PyAny>) -> PyResult<bool> {
        let typing = py.import_bound("typing")?;
        let builtins = py.import_bound("builtins")?;

        // Check for TypedDict
        let is_typeddict = typing.getattr("is_typeddict")?;
        if is_typeddict.call1((target,))?.is_truthy()? {
            return Ok(true);
        }

        // Check for dataclass
        let dataclasses = py.import_bound("dataclasses")?;
        let is_dataclass = dataclasses.getattr("is_dataclass")?;
        let type_type = builtins.getattr("type")?;
        let isinstance = builtins.getattr("isinstance")?;
        if is_dataclass.call1((target,))?.is_truthy()?
            && isinstance.call1((target, &type_type))?.is_truthy()?
        {
            return Ok(true);
        }

        // Check for NamedTuple
        if self.is_namedtuple(py, target)? {
            return Ok(true);
        }

        // Check generic args recursively
        let get_args = typing.getattr("get_args")?;
        let args = get_args.call1((target,))?;
        for arg in args.iter()? {
            let arg = arg?;
            if self.contains_structured_type(py, &arg)? {
                return Ok(true);
            }
        }

        Ok(false)
    }

    /// Build a CompiledValidator for a type.
    fn build_validator(
        &self,
        py: Python<'_>,
        target: &Bound<'_, PyAny>,
    ) -> PyResult<CompiledValidator> {
        let typing = py.import_bound("typing")?;
        let builtins = py.import_bound("builtins")?;

        // Check for primitive types first
        let int_type = builtins.getattr("int")?;
        let float_type = builtins.getattr("float")?;
        let str_type = builtins.getattr("str")?;
        let bool_type = builtins.getattr("bool")?;
        let none_type = builtins.getattr("type")?.call1((py.None(),))?;

        if target.is(&int_type) {
            return Ok(CompiledValidator::Int);
        }
        if target.is(&float_type) {
            return Ok(CompiledValidator::Float);
        }
        if target.is(&str_type) {
            return Ok(CompiledValidator::Str);
        }
        if target.is(&bool_type) {
            return Ok(CompiledValidator::Bool);
        }
        if target.is(&none_type) {
            return Ok(CompiledValidator::None);
        }

        // Check for Any
        let any_type = typing.getattr("Any")?;
        if target.is(&any_type) {
            return Ok(CompiledValidator::Any);
        }

        // Get origin and args for generic types
        let get_origin = typing.getattr("get_origin")?;
        let get_args = typing.getattr("get_args")?;

        let origin = get_origin.call1((target,))?;
        let args: Bound<'_, PyTuple> = get_args.call1((target,))?.downcast_into()?;

        // Check if it's a Union type (including | syntax)
        let union_type = typing.getattr("Union")?;
        let types_module = py.import_bound("types")?;
        let union_type_class = types_module.getattr("UnionType")?;

        if (!origin.is_none() && origin.is(&union_type))
            || target.is_instance(&union_type_class)?
        {
            return self.build_union_validator(py, target, &args, &none_type);
        }

        // Check for container types
        let list_type = builtins.getattr("list")?;
        let dict_type = builtins.getattr("dict")?;
        let tuple_type = builtins.getattr("tuple")?;
        let set_type = builtins.getattr("set")?;
        let frozenset_type = builtins.getattr("frozenset")?;

        let origin_ref = &origin;
        let origin_or_target = if origin_ref.is_none() {
            target
        } else {
            origin_ref
        };

        if origin_or_target.is(&list_type) {
            return self.build_list_validator(py, target, &args);
        }
        if origin_or_target.is(&dict_type) {
            return self.build_dict_validator(py, target, &args);
        }
        if origin_or_target.is(&tuple_type) {
            return self.build_tuple_validator(py, target, &args);
        }
        if origin_or_target.is(&set_type) {
            return self.build_set_validator(py, target, &args);
        }
        if origin_or_target.is(&frozenset_type) {
            return self.build_frozenset_validator(py, target, &args);
        }

        // Check for Literal
        let literal_type = typing.getattr("Literal")?;
        if !origin_ref.is_none() && origin_ref.is(&literal_type) {
            return self.build_literal_validator(py, target, &args);
        }

        // Note: TypedDict, dataclass, NamedTuple are handled earlier in compile()
        // via contains_structured_type() check, which delegates entire type to Python

        // Unsupported type - return an error for now
        Err(pyo3::exceptions::PyTypeError::new_err(format!(
            "Unsupported type: {}",
            target.repr()?
        )))
    }

    fn build_list_validator(
        &self,
        py: Python<'_>,
        target: &Bound<'_, PyAny>,
        args: &Bound<'_, PyTuple>,
    ) -> PyResult<CompiledValidator> {
        if args.is_empty() {
            return Ok(CompiledValidator::ListUntyped {
                target: target.clone().unbind(),
            });
        }

        let elem_type = args.get_item(0)?;
        let elem_validator = self.compile(py, &elem_type)?;

        Ok(CompiledValidator::List {
            target: target.clone().unbind(),
            elem: Box::new(elem_validator),
        })
    }

    fn build_dict_validator(
        &self,
        py: Python<'_>,
        target: &Bound<'_, PyAny>,
        args: &Bound<'_, PyTuple>,
    ) -> PyResult<CompiledValidator> {
        if args.is_empty() {
            return Ok(CompiledValidator::DictUntyped {
                target: target.clone().unbind(),
            });
        }

        let key_type = args.get_item(0)?;
        let val_type = args.get_item(1)?;
        let val_validator = self.compile(py, &val_type)?;

        // Optimize for dict[str, T]
        let builtins = py.import_bound("builtins")?;
        let str_type = builtins.getattr("str")?;
        if key_type.is(&str_type) {
            return Ok(CompiledValidator::DictStrKey {
                target: target.clone().unbind(),
                val: Box::new(val_validator),
            });
        }

        let key_validator = self.compile(py, &key_type)?;

        Ok(CompiledValidator::Dict {
            target: target.clone().unbind(),
            key: Box::new(key_validator),
            val: Box::new(val_validator),
        })
    }

    fn build_tuple_validator(
        &self,
        py: Python<'_>,
        target: &Bound<'_, PyAny>,
        args: &Bound<'_, PyTuple>,
    ) -> PyResult<CompiledValidator> {
        if args.is_empty() {
            return Ok(CompiledValidator::TupleUntyped {
                target: target.clone().unbind(),
            });
        }

        // Check for tuple[T, ...] (homogeneous)
        if args.len() == 2 {
            let second = args.get_item(1)?;
            let builtins = py.import_bound("builtins")?;
            let ellipsis_type = builtins.getattr("Ellipsis")?;
            if second.is(&ellipsis_type) {
                let elem_type = args.get_item(0)?;
                let elem_validator = self.compile(py, &elem_type)?;
                return Ok(CompiledValidator::TupleHomogeneous {
                    target: target.clone().unbind(),
                    elem: Box::new(elem_validator),
                });
            }
        }

        // Fixed-length tuple
        let elem_validators: Vec<CompiledValidator> = args
            .iter()
            .map(|t| self.compile(py, &t))
            .collect::<PyResult<Vec<_>>>()?;

        Ok(CompiledValidator::Tuple {
            target: target.clone().unbind(),
            elems: elem_validators,
        })
    }

    fn build_set_validator(
        &self,
        py: Python<'_>,
        target: &Bound<'_, PyAny>,
        args: &Bound<'_, PyTuple>,
    ) -> PyResult<CompiledValidator> {
        if args.is_empty() {
            return Ok(CompiledValidator::SetUntyped {
                target: target.clone().unbind(),
            });
        }

        let elem_type = args.get_item(0)?;
        let elem_validator = self.compile(py, &elem_type)?;

        Ok(CompiledValidator::Set {
            target: target.clone().unbind(),
            elem: Box::new(elem_validator),
        })
    }

    fn build_frozenset_validator(
        &self,
        py: Python<'_>,
        target: &Bound<'_, PyAny>,
        args: &Bound<'_, PyTuple>,
    ) -> PyResult<CompiledValidator> {
        if args.is_empty() {
            return Ok(CompiledValidator::FrozenSetUntyped {
                target: target.clone().unbind(),
            });
        }

        let elem_type = args.get_item(0)?;
        let elem_validator = self.compile(py, &elem_type)?;

        Ok(CompiledValidator::FrozenSet {
            target: target.clone().unbind(),
            elem: Box::new(elem_validator),
        })
    }

    fn build_union_validator(
        &self,
        py: Python<'_>,
        target: &Bound<'_, PyAny>,
        args: &Bound<'_, PyTuple>,
        none_type: &Bound<'_, PyAny>,
    ) -> PyResult<CompiledValidator> {
        let args_vec: Vec<Bound<'_, PyAny>> = args.iter().collect();

        // Optimize for Optional[T] (T | None)
        if args_vec.len() == 2 {
            let has_none = args_vec.iter().any(|t| t.is(none_type));
            if has_none {
                let other_type = args_vec.iter().find(|t| !t.is(none_type)).unwrap();
                let inner_validator = self.compile(py, other_type)?;
                return Ok(CompiledValidator::Optional {
                    inner: Box::new(inner_validator),
                });
            }
        }

        // Check if all types are primitives
        let builtins = py.import_bound("builtins")?;
        let int_type = builtins.getattr("int")?;
        let float_type = builtins.getattr("float")?;
        let str_type = builtins.getattr("str")?;
        let bool_type = builtins.getattr("bool")?;

        let all_primitives = args_vec.iter().all(|t| {
            t.is(&int_type)
                || t.is(&float_type)
                || t.is(&str_type)
                || t.is(&bool_type)
                || t.is(none_type)
        });

        if all_primitives {
            let has_int = args_vec.iter().any(|t| t.is(&int_type));
            let has_float = args_vec.iter().any(|t| t.is(&float_type));
            let has_str = args_vec.iter().any(|t| t.is(&str_type));
            let has_bool = args_vec.iter().any(|t| t.is(&bool_type));
            let has_none = args_vec.iter().any(|t| t.is(none_type));

            // Check if float comes before int
            let float_idx = args_vec.iter().position(|t| t.is(&float_type));
            let int_idx = args_vec.iter().position(|t| t.is(&int_type));
            let float_before_int = match (float_idx, int_idx) {
                (Some(f), Some(i)) => f < i,
                _ => false,
            };

            return Ok(CompiledValidator::PrimitiveUnion {
                target: target.clone().unbind(),
                info: PrimitiveUnionInfo::new(
                    has_int,
                    has_float,
                    has_str,
                    has_bool,
                    has_none,
                    float_before_int,
                ),
            });
        }

        // Optimize for 2-type union
        if args_vec.len() == 2 {
            let v0 = self.compile(py, &args_vec[0])?;
            let v1 = self.compile(py, &args_vec[1])?;
            return Ok(CompiledValidator::Union2 {
                target: target.clone().unbind(),
                v0: Box::new(v0),
                v1: Box::new(v1),
            });
        }

        // General union
        let validators: Vec<CompiledValidator> = args_vec
            .iter()
            .map(|t| self.compile(py, t))
            .collect::<PyResult<Vec<_>>>()?;

        Ok(CompiledValidator::Union {
            target: target.clone().unbind(),
            validators,
        })
    }

    fn build_literal_validator(
        &self,
        _py: Python<'_>,
        target: &Bound<'_, PyAny>,
        args: &Bound<'_, PyTuple>,
    ) -> PyResult<CompiledValidator> {
        let allowed: Vec<PyObject> = args.iter().map(|v| v.unbind()).collect();

        Ok(CompiledValidator::Literal {
            target: target.clone().unbind(),
            allowed,
        })
    }

    /// Delegate to Python's compiled validator for TypedDict, dataclass, NamedTuple.
    /// Python's code generation produces faster validators for these types.
    fn build_python_delegate(
        &self,
        py: Python<'_>,
        target: &Bound<'_, PyAny>,
    ) -> PyResult<CompiledValidator> {
        // Use frfr's internal default validator to get a compiled validator
        // This reuses Python's cached validators instead of creating new ones
        let frfr_validation = py.import_bound("frfr.validation")?;
        let default_validator = frfr_validation.getattr("_DEFAULT_VALIDATOR")?;

        // Call the internal _compile method to get a compiled validator
        let compiled = default_validator.call_method1("_compile", (target,))?;

        Ok(CompiledValidator::PythonDelegate {
            validator: compiled.unbind(),
        })
    }

    fn is_namedtuple(&self, py: Python<'_>, target: &Bound<'_, PyAny>) -> PyResult<bool> {
        // A NamedTuple is a subclass of tuple with _fields attribute
        let builtins = py.import_bound("builtins")?;
        let tuple_type = builtins.getattr("tuple")?;

        if !target.is_instance_of::<pyo3::types::PyType>() {
            return Ok(false);
        }

        let is_tuple_subclass = target
            .downcast::<pyo3::types::PyType>()?
            .is_subclass(&tuple_type)?;

        if !is_tuple_subclass {
            return Ok(false);
        }

        // Check for _fields attribute
        Ok(target.hasattr("_fields")?)
    }
}

/// Default validator instance.
static DEFAULT_VALIDATOR: std::sync::OnceLock<Validator> = std::sync::OnceLock::new();

fn get_default_validator() -> &'static Validator {
    DEFAULT_VALIDATOR.get_or_init(|| Validator::new(true))
}

/// Validate data against a type using the default validator.
#[pyfunction]
pub fn validate(
    py: Python<'_>,
    target: &Bound<'_, PyAny>,
    data: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    get_default_validator().validate(py, target, data)
}

/// Python module definition.
#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Validator>()?;
    m.add_class::<ValidationError>()?;
    m.add_function(wrap_pyfunction!(validate, m)?)?;
    Ok(())
}
