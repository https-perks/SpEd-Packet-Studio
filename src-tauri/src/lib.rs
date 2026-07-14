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
        let output = std::process::Command::new("powershell")
            .arg("-NoProfile")
            .arg("-STA")
            .arg("-Command")
            .arg(script)
            .output()
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
        let output = std::process::Command::new("powershell")
            .arg("-NoProfile")
            .arg("-STA")
            .arg("-Command")
            .arg(script)
            .output()
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            open_path,
            select_folder,
            select_save_file,
            copy_export_to
        ])
        .run(tauri::generate_context!())
        .expect("error while running SpEd Packet Studio");
}
