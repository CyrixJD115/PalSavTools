fn main() {
    #[cfg(target_os = "windows")]
    {
        let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap();
        let binaries_dir = std::path::Path::new(&manifest_dir).join("binaries");
        std::fs::create_dir_all(&binaries_dir).unwrap();

        let exe_path = binaries_dir.join("pst-backend-x86_64-pc-windows-msvc.exe");
        if !exe_path.exists() {
            let project_root = std::path::Path::new(&manifest_dir)
                .parent().unwrap()
                .parent().unwrap()
                .parent().unwrap();

            // Create .cmd launcher for reference
            let cmd_content = format!(
                "@echo off\r\ncd /d \"{}\"\r\nuv run python app/backend/main.py\r\n",
                project_root.to_str().unwrap()
            );
            std::fs::write(
                binaries_dir.join("pst-backend-x86_64-pc-windows-msvc.cmd"),
                cmd_content,
            )
            .unwrap();
            println!("cargo:warning=Created sidecar .cmd launcher");

            // Dummy .exe to pass tauri_build::build() file-existence check.
            // In debug/dev mode lib.rs skips the sidecar spawn (backend is
            // already started by main.py), so this never executes.
            std::fs::write(&exe_path, b"").unwrap();
            println!("cargo:warning=Created sidecar .exe placeholder (dev-only)");
        }
    }
    tauri_build::build()
}
