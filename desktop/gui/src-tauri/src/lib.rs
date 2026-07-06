use std::{
    fs::OpenOptions,
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
};

use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let backend = backend_command(app);
            let workdir = backend_workdir(app);
            let logdir = workdir.clone();
            let stdout = OpenOptions::new()
                .create(true)
                .append(true)
                .open(logdir.join("backend.stdout.log"))
                .ok()
                .map(Stdio::from)
                .unwrap_or_else(Stdio::null);
            let stderr = OpenOptions::new()
                .create(true)
                .append(true)
                .open(logdir.join("backend.stderr.log"))
                .ok()
                .map(Stdio::from)
                .unwrap_or_else(Stdio::null);
            let _ = std::fs::write(
                logdir.join("backend-launch.log"),
                format!("program={}\nworkdir={}\n", backend.program.display(), workdir.display()),
            );
            let mut command = Command::new(backend.program);
            for arg in backend.args {
                command.arg(arg);
            }
            let child = command
                .env("WEUNIX_BACKEND_PORT", "8765")
                .env("WEUNIX_WORKDIR", &workdir)
                .current_dir(&workdir)
                .stdout(stdout)
                .stderr(stderr)
                .spawn()
                .ok();
            app.manage(BackendProcess(Mutex::new(child)));
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::Destroyed) {
                let state = window.state::<BackendProcess>();
                let child_result = state.0.lock();
                if let Ok(mut child) = child_result {
                    if let Some(mut process) = child.take() {
                        let _ = process.kill();
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Weunix desktop");
}

struct BackendCommand {
    program: PathBuf,
    args: Vec<String>,
}

fn backend_command(app: &tauri::App) -> BackendCommand {
    if cfg!(debug_assertions) {
        let script = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(|path| path.parent())
            .expect("desktop parent")
            .join("backend_api.py");
        BackendCommand {
            program: PathBuf::from("py"),
            args: vec!["-3".to_string(), script.to_string_lossy().to_string()],
        }
    } else {
        let backend = release_backend_path(app);
        BackendCommand {
            program: backend,
            args: Vec::new(),
        }
    }
}

fn release_backend_path(app: &tauri::App) -> PathBuf {
    let mut candidates = Vec::new();
    if let Ok(resource_dir) = app.path().resource_dir() {
        candidates.push(resource_dir.join("weunix-backend.exe"));
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            candidates.push(parent.join("resources").join("weunix-backend.exe"));
            candidates.push(parent.join("weunix-backend.exe"));
        }
    }
    candidates
        .into_iter()
        .find(|path| path.exists())
        .unwrap_or_else(|| PathBuf::from("weunix-backend.exe"))
}

fn backend_workdir(app: &tauri::App) -> PathBuf {
    if cfg!(debug_assertions) {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(|path| path.parent())
            .and_then(|path| path.parent())
            .expect("project root")
            .to_path_buf()
    } else {
        let dir = app
            .path()
            .app_data_dir()
            .expect("app data dir");
        let _ = std::fs::create_dir_all(&dir);
        dir
    }
}
