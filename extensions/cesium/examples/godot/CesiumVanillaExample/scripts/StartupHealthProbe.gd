extends SceneTree


const PROBED_CLASSES := [
	"CesiumGeoreference",
	"Cesium3DTileset",
	"CesiumIonRasterOverlay",
]


func _init() -> void:
	var user_dir := ProjectSettings.globalize_path("user://")
	var shader_cache := ProjectSettings.globalize_path("user://shader_cache")
	var probe_file := user_dir.path_join("startup_health_probe.txt")
	var report := {
		"user_dir": user_dir,
		"shader_cache": shader_cache,
		"user_dir_mkdir_ok": DirAccess.make_dir_recursive_absolute(user_dir) == OK,
		"shader_cache_mkdir_ok": DirAccess.make_dir_recursive_absolute(shader_cache) == OK,
		"scratch_write_ok": false,
		"classes": {},
	}
	var file := FileAccess.open(probe_file, FileAccess.WRITE)
	if file != null:
		file.store_line("startup health probe")
		report["scratch_write_ok"] = true
	for class_name in PROBED_CLASSES:
		report["classes"][class_name] = ClassDB.class_exists(class_name)
	print(JSON.stringify(report))
	quit(0 if report["shader_cache_mkdir_ok"] and report["scratch_write_ok"] else 1)
