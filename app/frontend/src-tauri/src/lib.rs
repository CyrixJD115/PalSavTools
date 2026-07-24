use std::sync::Mutex;

use tauri::Manager;
#[cfg(not(debug_assertions))]
use tauri_plugin_shell::ShellExt;

struct BackendState {
    child: Option<tauri_plugin_shell::process::CommandChild>,
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(Mutex::new(BackendState { child: None }))
        .setup(|_app| {
            #[cfg(not(debug_assertions))]
            {
                let app = _app;
                let sidecar = app
                    .shell()
                    .sidecar("pst-backend")
                    .expect("failed to create sidecar command");

                let (mut rx, child) = sidecar.spawn().expect("failed to spawn sidecar");

                let state = app.state::<Mutex<BackendState>>();
                state.lock().unwrap().child = Some(child);

                tauri::async_runtime::spawn(async move {
                    use tauri_plugin_shell::process::CommandEvent;
                    while let Some(event) = rx.recv().await {
                        match event {
                            CommandEvent::Stdout(line) => {
                                println!("[backend] {}", String::from_utf8_lossy(&line));
                            }
                            CommandEvent::Stderr(line) => {
                                eprintln!("[backend] {}", String::from_utf8_lossy(&line));
                            }
                            CommandEvent::Terminated(payload) => {
                                eprintln!(
                                    "[backend] exited (code={:?}, signal={:?})",
                                    payload.code, payload.signal
                                );
                                break;
                            }
                            _ => {}
                        }
                    }
                });
            }

            #[cfg(debug_assertions)]
            {
                println!("[backend] dev mode — backend managed externally");
            }

            // Poll health endpoint until backend is ready
            let client = reqwest::blocking::Client::builder()
                .timeout(std::time::Duration::from_secs(2))
                .build()
                .unwrap();

            let max_retries = 30;
            let mut ready = false;
            for _ in 0..max_retries {
                if let Ok(resp) = client.get("http://127.0.0.1:16921/api/health").send() {
                    if resp.status().is_success() {
                        ready = true;
                        break;
                    }
                }
                std::thread::sleep(std::time::Duration::from_millis(500));
            }

            if ready {
                println!("[backend] health check passed");
            } else {
                eprintln!("[backend] health check failed after {max_retries} retries");
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app_handle, event| {
        if let tauri::RunEvent::ExitRequested { .. } = &event {
            let state = app_handle.state::<Mutex<BackendState>>();
            let child = state.lock().unwrap().child.take();
            if let Some(c) = child {
                let _ = c.kill();
                println!("[backend] killed");
            }
        }
    });
}
