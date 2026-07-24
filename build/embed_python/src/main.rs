//! Proof of concept: a native Rust binary embeds CPython and executes a Python
//! module whose source lives **inside the binary** (no `.py` file on disk).
//!
//! See README.md for the runtime/link requirements (python-build-standalone).

use std::env;
use std::ffi::CString;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};

// Python sources compiled into the binary at build time. No .py shipped.
static FINDER_BOOTSTRAP: &str = include_str!("../python_src/finder_bootstrap.py");
static PST_EMBED_SRC: &str = include_str!("../python_src/pst_embed.py");

fn main() -> PyResult<()> {
    // Point the embedded CPython at the bundled stdlib/runtime BEFORE the
    // interpreter initializes (PBS compiles with prefix=/install, which does
    // not exist on the host). In the real app this path comes from the Tauri
    // resource dir; here it's configurable via env, default ./python.
    if env::var_os("PYTHONHOME").is_none() {
        let home = env::var("PST_PYTHON_HOME").unwrap_or_else(|_| "python".to_string());
        env::set_var("PYTHONHOME", home);
    }

    Python::attach(|py| {
        println!("[rust] Python interpreter attached: {}", Python::version_str());

        // --- 1. Boot the in-memory finder from source embedded in the binary ---
        // Run the bootstrap source directly: its top-level defs (`register`)
        // land in our `locals` dict, so we can call it next.
        let locals = PyDict::new(py);
        py.run(
            &CString::new(FINDER_BOOTSTRAP).expect("bootstrap is valid C string"),
            Some(&locals),
            Some(&locals),
        )?;

        // --- 2. Register our embedded module(s) ---
        // Build { "pst_embed": b"<source>" } and hand it to register().
        let modules = PyDict::new(py);
        modules.set_item("pst_embed", PyBytes::new(py, PST_EMBED_SRC.as_bytes()))?;
        let register = locals
            .get_item("register")?
            .expect("register() defined by the bootstrap");
        register.call1((modules,))?;

        // --- 3. Import pst_embed — resolved by OUR finder, never from disk ---
        let pst = py.import("pst_embed")?;
        println!("[rust] imported 'pst_embed' from in-memory source");

        // --- 4. Call Python's add(10, 20) and prove the result crosses back to Rust ---
        let result: i64 = pst.getattr("add")?.call1((10i64, 20i64))?.extract()?;
        println!("[rust] pst_embed.add(10, 20) = {result}");
        assert_eq!(result, 30, "Rust<->Python roundtrip must return 30");

        // --- 5. Bonus: call whoami() to prove the module truly ran from memory ---
        let msg: String = pst.getattr("whoami")?.call0()?.extract()?;
        println!("[rust] pst_embed.whoami() -> {msg}");

        Ok(())
    })
}
