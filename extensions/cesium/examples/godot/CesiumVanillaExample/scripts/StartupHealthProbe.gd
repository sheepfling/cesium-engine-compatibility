extends SceneTree

# Version marker: this probe is part of the Godot 4.x proof lane and is
# exercised against the version set tracked in the repo notes.


func _initialize() -> void:
	print("startup health probe starting")
	var user_dir := ProjectSettings.globalize_path("user://")
	var shader_cache := ProjectSettings.globalize_path("user://shader_cache")
	var probe_file := user_dir.path_join("startup_health_probe.txt")
	var report := {
		"user_dir": user_dir,
		"shader_cache": shader_cache,
		"user_dir_mkdir_ok": DirAccess.make_dir_recursive_absolute(user_dir) == OK,
		"shader_cache_mkdir_ok": DirAccess.make_dir_recursive_absolute(shader_cache) == OK,
		"scratch_write_ok": false,
	}
	var file := FileAccess.open(probe_file, FileAccess.WRITE)
	if file != null:
		file.store_line("startup health probe")
		report["scratch_write_ok"] = true
	print(JSON.stringify(report))
	quit(0 if report["shader_cache_mkdir_ok"] and report["scratch_write_ok"] else 1)
