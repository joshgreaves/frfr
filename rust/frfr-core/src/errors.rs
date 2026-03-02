//! Validation error types.

use pyo3::prelude::*;

/// Error raised when validation fails.
#[pyclass(extends=pyo3::exceptions::PyException, module="frfr._core")]
#[derive(Clone)]
pub struct ValidationError {
    #[pyo3(get)]
    pub expected: PyObject,
    #[pyo3(get)]
    pub actual: PyObject,
    #[pyo3(get)]
    pub path: String,
}

#[pymethods]
impl ValidationError {
    #[new]
    #[pyo3(signature = (expected, actual, path = String::new()))]
    pub fn new(expected: PyObject, actual: PyObject, path: String) -> Self {
        ValidationError {
            expected,
            actual,
            path,
        }
    }

    pub fn __str__(&self, py: Python<'_>) -> PyResult<String> {
        let actual_type = self.actual.bind(py).get_type().name()?;
        let actual_repr = self.actual.bind(py).repr()?.to_string();

        // Get expected name - handle both types and type forms
        let expected_name = if let Ok(name) = self.expected.bind(py).getattr("__name__") {
            name.to_string()
        } else {
            self.expected.bind(py).str()?.to_string()
        };

        let location = if self.path.is_empty() {
            String::new()
        } else {
            format!("{} - ", self.path)
        };

        Ok(format!(
            "{}expected {}, got {} ({})",
            location, expected_name, actual_type, actual_repr
        ))
    }

    pub fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let msg = self.__str__(py)?;
        Ok(format!("ValidationError('{}')", msg))
    }
}

/// Create a ValidationError for a primitive type.
pub fn primitive_error(py: Python<'_>, type_name: &str, actual: &Bound<'_, PyAny>) -> PyErr {
    let builtins = py.import_bound("builtins").unwrap();
    let expected = builtins.getattr(type_name).unwrap().unbind();
    PyErr::new::<ValidationError, _>((expected, actual.clone().unbind(), String::new()))
}

/// Create a ValidationError for a union type.
pub fn union_error(_py: Python<'_>, target: PyObject, actual: &Bound<'_, PyAny>) -> PyErr {
    PyErr::new::<ValidationError, _>((target, actual.clone().unbind(), String::new()))
}

/// Create a ValidationError with a path.
pub fn error_with_path(
    target: PyObject,
    actual: &Bound<'_, PyAny>,
    path: &str,
) -> PyErr {
    PyErr::new::<ValidationError, _>((target, actual.clone().unbind(), path.to_string()))
}
