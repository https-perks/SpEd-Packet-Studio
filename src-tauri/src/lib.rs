#[tauri::command]
fn open_path(path: String) -> Result<(), String> {
    let path = std::path::PathBuf::from(path);
    if !path.exists() {
        return Err("The exported file does not exist.".to_string());
    }

    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("explorer")
            .arg(&path)
            .spawn()
            .map_err(|error| format!("Could not open the exported file: {error}"))?;
    }

    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(&path)
            .spawn()
            .map_err(|error| format!("Could not open the exported file: {error}"))?;
    }

    #[cfg(all(unix, not(target_os = "macos")))]
    {
        std::process::Command::new("xdg-open")
            .arg(&path)
            .spawn()
            .map_err(|error| format!("Could not open the exported file: {error}"))?;
    }

    Ok(())
}

#[tauri::command]
fn select_folder() -> Result<Option<String>, String> {
    #[cfg(target_os = "windows")]
    {
        let script = r#"
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Choose where exported packets should be saved'
$dialog.ShowNewFolderButton = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  [Console]::Out.Write($dialog.SelectedPath)
}
"#;
        let output = run_hidden_powershell(script)
            .map_err(|error| format!("Could not open the folder picker: {error}"))?;
        if !output.status.success() {
            return Err("The folder picker did not complete successfully.".to_string());
        }
        let value = String::from_utf8_lossy(&output.stdout).trim().to_string();
        return Ok(if value.is_empty() { None } else { Some(value) });
    }

    #[cfg(not(target_os = "windows"))]
    {
        Ok(None)
    }
}

#[tauri::command]
fn select_save_file(suggested_filename: String, extension: String) -> Result<Option<String>, String> {
    #[cfg(target_os = "windows")]
    {
        let safe_filename = suggested_filename.replace('\'', "''");
        let safe_extension = extension.trim_start_matches('.').replace('\'', "''");
        let filter_label = if safe_extension.eq_ignore_ascii_case("zip") {
            "ZIP archives"
        } else {
            "PDF files"
        };
        let script = format!(
            r#"
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.SaveFileDialog
$dialog.Title = 'Export packet'
$dialog.FileName = '{safe_filename}'
$dialog.DefaultExt = '{safe_extension}'
$dialog.Filter = '{filter_label} (*.{safe_extension})|*.{safe_extension}|All files (*.*)|*.*'
$dialog.OverwritePrompt = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
  [Console]::Out.Write($dialog.FileName)
}}
"#
        );
        let output = run_hidden_powershell(&script)
            .map_err(|error| format!("Could not open the save dialog: {error}"))?;
        if !output.status.success() {
            return Err("The save dialog did not complete successfully.".to_string());
        }
        let value = String::from_utf8_lossy(&output.stdout).trim().to_string();
        return Ok(if value.is_empty() { None } else { Some(value) });
    }

    #[cfg(not(target_os = "windows"))]
    {
        let _ = suggested_filename;
        let _ = extension;
        Ok(None)
    }
}

#[tauri::command]
fn copy_export_to(source_path: String, destination_path: String) -> Result<(), String> {
    let source = std::path::PathBuf::from(source_path);
    let destination = std::path::PathBuf::from(destination_path);
    if !source.exists() {
        return Err("The generated export file does not exist.".to_string());
    }
    if let Some(parent) = destination.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|error| format!("Could not prepare the export folder: {error}"))?;
    }
    std::fs::copy(&source, &destination)
        .map_err(|error| format!("Could not save the exported packet: {error}"))?;
    Ok(())
}

#[cfg(target_os = "windows")]
fn run_hidden_powershell(script: &str) -> std::io::Result<std::process::Output> {
    use std::os::windows::process::CommandExt;

    const CREATE_NO_WINDOW: u32 = 0x08000000;
    std::process::Command::new("powershell")
        .arg("-NoProfile")
        .arg("-STA")
        .arg("-Command")
        .arg(script)
        .creation_flags(CREATE_NO_WINDOW)
        .output()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendState(Mutex::new(None)))
        .setup(|app| {
            configure_backend_paths(app)?;
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if let Err(error) = start_backend(app_handle) {
                    eprintln!("Backend launch failed: {error}");
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            open_path,
            select_folder,
            select_save_file,
            copy_export_to
        ])
        ;
    let app = match builder.build(tauri::generate_context!()) {
        Ok(app) => app,
        Err(error) => {
            show_startup_error(&format!("SpEd Packet Studio could not start.\n\n{error}"));
            return;
        }
    };
    app.run(|app_handle, event| {
        if let RunEvent::ExitRequested { .. } = event {
            stop_backend(app_handle);
        }
    });
}

fn configure_backend_paths(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let root = app.path().local_data_dir()?.join("SpEd Packet Studio");
    let resource_dir = app.path().resource_dir()?;
    let resources = if resource_dir.join("_up_").is_dir() {
        resource_dir.join("_up_")
    } else {
        resource_dir
    };
    for name in ["data", "settings", "templates", "brand-kits", "imports", "backups", "logs", "cache", "temp"] {
        std::fs::create_dir_all(root.join(name))?;
    }
    std::env::set_var("SPED_PACKET_APP_DATA_DIR", &root);
    std::env::set_var("SPED_PACKET_RESOURCE_DIR", &resources);
    std::env::set_var("SPED_PACKET_CACHE_DIR", root.join("cache"));
    std::env::set_var("SPED_PACKET_TEMP_DIR", root.join("temp"));
    std::env::set_var("SPED_PACKET_LOG_DIR", root.join("logs"));
    std::env::set_var("PACKET_STUDIO_API_HOST", BACKEND_HOST);
    std::env::set_var("PACKET_STUDIO_API_PORT", BACKEND_PORT.to_string());
    std::env::set_var("PACKET_STUDIO_ENV", "packaged");
    std::env::set_var("SPED_PACKET_PARENT_PID", std::process::id().to_string());
    Ok(())
}

fn start_backend(app: AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    if cfg!(debug_assertions) {
        return Ok(());
    }
    let listener = TcpListener::bind((BACKEND_HOST, BACKEND_PORT)).map_err(|error| {
        format!("Backend port {BACKEND_HOST}:{BACKEND_PORT} is unavailable. Close another SpEd Packet Studio instance or the program using that port. ({error})")
    })?;
    drop(listener);
    let logs_dir = app.path().local_data_dir()?.join("SpEd Packet Studio").join("logs");
    let stdout_log = logs_dir.join("backend-sidecar.stdout.log");
    let stderr_log = logs_dir.join("backend-sidecar.stderr.log");
    let command = app.shell().sidecar("sped-packet-backend")?;
    let (mut events, child) = command.spawn()?;
    *app.state::<BackendState>().0.lock().map_err(|_| "backend state lock poisoned")? = Some(ManagedBackend {
        child,
    });
    let event_stdout_log = stdout_log.clone();
    let event_stderr_log = stderr_log.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = events.recv().await {
            match event {
                CommandEvent::Stdout(line) => append_log(&event_stdout_log, &line),
                CommandEvent::Stderr(line) => append_log(&event_stderr_log, &line),
                CommandEvent::Terminated(payload) => {
                    append_log(&event_stderr_log, format!("backend terminated: {payload:?}\n").as_bytes());
                }
                _ => {}
            }
        }
    });
    append_log(
        &stdout_log,
        format!(
            "backend launch requested for SpEd Packet Studio {}\n",
            env!("CARGO_PKG_VERSION")
        )
        .as_bytes(),
    );
    Ok(())
}

fn stop_backend(app: &tauri::AppHandle) {
    if let Ok(mut state) = app.state::<BackendState>().0.lock() {
        if let Some(backend) = state.take() {
            let _ = backend.child.kill();
        }
    }
}

fn append_log(path: &Path, content: &[u8]) {
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
        let _ = file.write_all(content);
        if !content.ends_with(b"\n") { let _ = file.write_all(b"\n"); }
    }
}

#[cfg(target_os = "windows")]
fn show_startup_error(message: &str) {
    use windows_sys::Win32::UI::WindowsAndMessaging::{MessageBoxW, MB_ICONERROR, MB_OK};
    let message: Vec<u16> = message.encode_utf16().chain(Some(0)).collect();
    let title: Vec<u16> = "SpEd Packet Studio startup error".encode_utf16().chain(Some(0)).collect();
    unsafe { MessageBoxW(std::ptr::null_mut(), message.as_ptr(), title.as_ptr(), MB_OK | MB_ICONERROR); }
}

#[cfg(not(target_os = "windows"))]
fn show_startup_error(message: &str) { eprintln!("{message}"); }
use std::fs::OpenOptions;
use std::io::Write;
use std::net::TcpListener;
use std::path::Path;
use std::sync::Mutex;
use tauri::{AppHandle, Manager, RunEvent};
use tauri_plugin_shell::{process::{CommandChild, CommandEvent}, ShellExt};

const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: u16 = 8765;

struct ManagedBackend {
    child: CommandChild,
}

struct BackendState(Mutex<Option<ManagedBackend>>);
