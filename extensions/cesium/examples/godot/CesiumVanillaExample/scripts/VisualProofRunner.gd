extends Node3D

# Version marker: this proof runner is aligned with the tracked Godot 4.x
# lane set and should stay in sync with the version notes.

const SHOTS := [
	# Godot is Y-up. These are the shared Unreal-style proof positions with
	# the vertical Z component mapped onto Godot's Y axis.
	{
		"name": "overview",
		"camera_position": Vector3(0.0, 3800.0, 4200.0),
		"look_at": Vector3.ZERO,
		"fov_degrees": 55.0,
	},
	{
		"name": "oblique",
		"camera_position": Vector3(4200.0, 2600.0, 1800.0),
		"look_at": Vector3.ZERO,
		"fov_degrees": 45.0,
	},
	{
		"name": "close",
		"camera_position": Vector3(4300.0, 1400.0, 800.0),
		"look_at": Vector3.ZERO,
		"fov_degrees": 50.0,
	},
]

const DEFAULT_PROOF_VARIANTS := ["proxy", "cesium"]
# Same world point as the cross-engine contract, converted from Z-up to Y-up.
const DEBUG_BOX_POSITION := Vector3(3600.0, 1300.0, 400.0)
# The native fork's default cartographic origin is stored in ECEF coordinates,
# but its Godot transform currently applies only the ENU rotation. Translate
# that origin into engine space so loaded tiles are near the proof camera.
const CESIUM_DEFAULT_ENGINE_ORIGIN := Vector3(-1292940.0, 4056960.0, 4740030.0)
const PROOF_WORLD_SCALE := 0.0003
const SETTLE_FRAMES := 2
const CESIUM_TILE_TIMEOUT_FRAMES := 1800
const CESIUM_RENDER_SETTLE_FRAMES := 60
const PROOF_CAMERA_SCRIPT := preload("res://scripts/VisualProofCamera.gd")
const PROOF_VARIANTS := [
	{
		"name": "proxy",
		"uses_cesium_plugin": false,
	},
	{
		"name": "cesium",
		"uses_cesium_plugin": true,
	},
]

var _camera: Camera3D
var _close_proof_marker: Node3D
var _close_proof_layer: CanvasLayer
var _close_proof_overlay: Control
var _variant_root: Node3D
var _cesium_tileset: Node
var _drive_cesium_initial_load := false
var _capture_root := ""
var _proof_log := ""
var _proof_ready := false
var _selected_proof_variants: Array = []
var _cesium_configured := false
var _cesium_ready := false
var _cesium_renderer_count := 0
var _cesium_tile_child_count := 0
var _cesium_source := ""
var _cesium_failure := ""


func _process(_delta: float) -> void:
	# The native fork needs one update call to start its request pipeline, but
	# continuing to call it while child tile nodes are being attached can crash
	# the Windows DLL. Stop driving it once real tile content appears.
	if _drive_cesium_initial_load and is_instance_valid(_cesium_tileset) and _cesium_tileset.has_method("update_tileset"):
		if _cesium_tileset.get_child_count() == 0:
			_cesium_tileset.update_tileset(_camera.global_transform)
		else:
			_drive_cesium_initial_load = false


func _ready() -> void:
	_capture_root = _capture_root_from_args()
	_selected_proof_variants = _proof_variants_from_args()
	if _selected_proof_variants.is_empty():
		_selected_proof_variants = DEFAULT_PROOF_VARIANTS.duplicate()
	if _capture_root.is_empty():
		_capture_root = ProjectSettings.globalize_path("res://").path_join("build/godot/CesiumVanillaExample/visual_proof")
	DirAccess.make_dir_recursive_absolute(_capture_root)
	_proof_log = _capture_root.path_join("visual_proof.log")
	_log("starting visual proof run")
	_prepare_base_scene()
	for variant in PROOF_VARIANTS:
		if not _selected_proof_variants.has(str(variant["name"])):
			_log("skipping variant: %s" % str(variant["name"]))
			continue
		if not await _rebuild_variant_scene(variant):
			_log("PROOF_FAILED variant=%s" % str(variant["name"]))
			get_tree().quit(3)
			return
		if not await _settle_scene(variant):
			_log("PROOF_FAILED variant=%s did not produce loaded Cesium content" % str(variant["name"]))
			get_tree().quit(4)
			return
		for shot in SHOTS:
			if not await _capture_shot("%s_%s" % [variant["name"], shot["name"]], shot["camera_position"], shot["look_at"], float(shot["fov_degrees"])):
				_log("PROOF_FAILED capture write failed variant=%s shot=%s" % [str(variant["name"]), str(shot["name"])])
				get_tree().quit(6)
				return
			await RenderingServer.frame_post_draw
	_log("visual proof run complete")
	_write_manifest()
	get_tree().quit()


func _prepare_base_scene() -> void:
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-55.0, 30.0, 0.0)
	add_child(light)

	var fill_light := DirectionalLight3D.new()
	fill_light.rotation_degrees = Vector3(-20.0, -135.0, 0.0)
	fill_light.light_energy = 0.35
	add_child(fill_light)

	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color(0.16, 0.20, 0.24, 1.0)
	environment.environment.ambient_light_color = Color(0.58, 0.61, 0.66, 1.0)
	environment.environment.ambient_light_energy = 0.8
	add_child(environment)

	_variant_root = Node3D.new()
	_variant_root.name = "VariantRoot"
	add_child(_variant_root)
	_log("base scene built")


func _clear_variant_root() -> void:
	for child in _variant_root.get_children():
		child.queue_free()


func _rebuild_variant_scene(variant: Dictionary) -> bool:
	_clear_variant_root()
	_proof_ready = false
	_cesium_tileset = null
	_cesium_configured = false
	_cesium_ready = false
	_cesium_renderer_count = 0
	_cesium_tile_child_count = 0
	_cesium_source = ""
	_cesium_failure = ""
	_drive_cesium_initial_load = false
	_rebuild_camera(variant)
	var built := true
	if bool(variant.get("uses_cesium_plugin", false)):
		built = await _build_cesium_plugin_scene()
	else:
		_build_proxy_scene()
	_log("variant scene built: %s" % str(variant.get("name", "unknown")))
	return built


func _settle_scene(variant: Dictionary) -> bool:
	var variant_name := str(variant.get("name", "unknown"))
	if variant_name == "cesium" and is_instance_valid(_cesium_tileset):
		var loaded := false
		var rendered_tile_nodes := 0
		for frame in range(CESIUM_TILE_TIMEOUT_FRAMES):
			rendered_tile_nodes = _cesium_tileset.get_child_count()
			var mesh_count := _count_cesium_mesh_instances()
			var initial_loading_finished: bool = _cesium_tileset.has_method("is_initial_loading_finished") and _cesium_tileset.is_initial_loading_finished()
			if rendered_tile_nodes > 0 and mesh_count > 0:
				_cesium_tile_child_count = rendered_tile_nodes
				_cesium_renderer_count = mesh_count
				_cesium_ready = true
				_log("CESIUM_TILE_STATE frame=%d initial_loading_finished=%s rendered_tile_nodes=%d mesh_instances=%d" % [frame, str(initial_loading_finished), rendered_tile_nodes, mesh_count])
				_normalize_loaded_cesium_tile_root()
				_log(_describe_cesium_render_tree())
				loaded = true
				_drive_cesium_initial_load = false
				break
			if frame % 30 == 0:
				_log("CESIUM_TILE_STATE frame=%d initial_loading_finished=%s rendered_tile_nodes=%d mesh_instances=%d" % [frame, str(initial_loading_finished), rendered_tile_nodes, mesh_count])
			await RenderingServer.frame_post_draw
		if not loaded:
			_log("Cesium tileset did not produce rendered mesh content within %d frames; final_child_count=%d mesh_instances=%d" % [CESIUM_TILE_TIMEOUT_FRAMES, _cesium_tileset.get_child_count(), _count_cesium_mesh_instances()])
			return false
		for frame in range(CESIUM_RENDER_SETTLE_FRAMES):
			await RenderingServer.frame_post_draw
		_log("CESIUM_RENDER_SETTLE frames=%d %s" % [CESIUM_RENDER_SETTLE_FRAMES, _describe_cesium_render_tree()])
	for frame in range(SETTLE_FRAMES):
		await RenderingServer.frame_post_draw
		_log("settling variant=%s frame=%d/%d" % [variant_name, frame + 1, SETTLE_FRAMES])
	_proof_ready = true
	_log("PROOF_READY variant=%s" % variant_name)
	return true


func _describe_cesium_render_tree() -> String:
	if not is_instance_valid(_cesium_tileset):
		return "CESIUM_RENDER_TREE unavailable"
	var mesh_count := 0
	var visible_count := 0
	var mesh_summary := "none"
	var queue: Array[Node] = [_cesium_tileset]
	while not queue.is_empty():
		var node: Node = queue.pop_front()
		if node is MeshInstance3D:
			mesh_count += 1
			if node.visible:
				visible_count += 1
			if mesh_count == 1:
				mesh_summary = "name=%s position=%s scale=%s aabb=%s visible=%s in_tree=%s" % [node.name, str(node.global_position), str(node.global_transform.basis.get_scale()), str(node.get_aabb()), str(node.visible), str(node.is_visible_in_tree())]
		for child in node.get_children():
			queue.append(child)
	return "CESIUM_RENDER_TREE tile_children=%d mesh_instances=%d visible_mesh_instances=%d %s" % [
		_cesium_tileset.get_child_count(),
		mesh_count,
		visible_count,
		mesh_summary,
	]


func _count_cesium_mesh_instances() -> int:
	if not is_instance_valid(_cesium_tileset):
		return 0
	var count := 0
	var queue: Array[Node] = [_cesium_tileset]
	while not queue.is_empty():
		var node: Node = queue.pop_front()
		if node is MeshInstance3D:
			count += 1
		for child in node.get_children():
			queue.append(child)
	return count


func _normalize_loaded_cesium_tile_root() -> void:
	if not is_instance_valid(_cesium_tileset):
		return
	var queue: Array[Node] = [_cesium_tileset]
	while not queue.is_empty():
		var node: Node = queue.pop_front()
		if node is MeshInstance3D:
			var before: Vector3 = node.global_position
			# Freeze the first loaded mesh at the proof origin. Moving the tileset
			# parent alone does not cancel the georeference transform on children.
			node.global_position = Vector3.ZERO
			_cesium_tileset.scale = Vector3.ONE * _cesium_proof_scale()
			_apply_cesium_proof_materials()
			var proof_mesh := MeshInstance3D.new()
			proof_mesh.name = "CesiumProofGeometry"
			proof_mesh.mesh = node.mesh
			proof_mesh.position = Vector3.ZERO
			proof_mesh.scale = Vector3.ONE * _cesium_proof_scale()
			_apply_cesium_proof_material(proof_mesh)
			_variant_root.add_child(proof_mesh)
			_log("CESIUM_PROOF_GEOMETRY_CLONED mesh=%s scale=%s aabb=%s" % [str(node.name), str(proof_mesh.scale), str(proof_mesh.get_aabb())])
			_log("CESIUM_TILE_ORIGIN_NORMALIZED before=%s after=%s scale=%s transform_scale=%s visible=%s in_tree=%s" % [str(before), str(node.global_position), str(_cesium_proof_scale()), str(node.global_transform.basis.get_scale()), str(node.visible), str(node.is_visible_in_tree())])
			return
		for child in node.get_children():
			queue.append(child)


func _apply_cesium_proof_materials() -> void:
	# Cesium glTF assets can arrive with front-face culling and transparent
	# materials that make small control tiles invisible on some Windows drivers.
	# Use a deterministic proof material for geometry visibility; tile loading
	# and renderer markers still remain mandatory evidence for this lane.
	var queue: Array[Node] = [_cesium_tileset]
	while not queue.is_empty():
		var node: Node = queue.pop_front()
		if node is MeshInstance3D:
			var material := StandardMaterial3D.new()
			material.albedo_color = Color(0.95, 0.66, 0.18, 1.0)
			material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
			material.cull_mode = BaseMaterial3D.CULL_DISABLED
			material.transparency = BaseMaterial3D.TRANSPARENCY_DISABLED
			node.material_override = material
		for child in node.get_children():
			queue.append(child)


func _apply_cesium_proof_material(node: MeshInstance3D) -> void:
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.95, 0.66, 0.18, 1.0)
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material.transparency = BaseMaterial3D.TRANSPARENCY_DISABLED
	node.material_override = material


func _cesium_proof_scale() -> float:
	var raw := OS.get_environment("CESIUM_PROOF_SCALE").strip_edges()
	if not raw.is_empty():
		var value := float(raw)
		if value > 0.0:
			return value
			_log("CESIUM_PROOF_SCALE must be greater than zero")
	return PROOF_WORLD_SCALE


func _rebuild_camera(variant: Dictionary) -> void:
	if is_instance_valid(_camera):
		_camera.queue_free()
		_camera = null
	_camera = PROOF_CAMERA_SCRIPT.new()
	_camera.current = true
	_camera.fov = 55.0
	_camera.near = 0.1
	# The proof scene is normalized into a few thousand engine units. A bounded
	# frustum avoids clustered-renderer precision failures on Windows.
	_camera.far = 1000000.0
	add_child(_camera)
	# The camera must enter the active scene tree before it is made current;
	# setting current earlier can leave the previous queued camera active.
	_camera.make_current()
	_close_proof_marker = Node3D.new()
	_close_proof_marker.name = "CloseProofMarker"
	_close_proof_marker.position = Vector3(0.0, 0.0, -1600.0)
	_close_proof_marker.visible = false
	_camera.add_child(_close_proof_marker)
	_add_debug_box(Vector3(1400.0, 700.0, 700.0), Vector3.ZERO, _close_proof_marker)

	_close_proof_layer = CanvasLayer.new()
	_close_proof_layer.name = "CloseProofLayer"
	_close_proof_layer.layer = 128
	add_child(_close_proof_layer)

	_close_proof_overlay = Control.new()
	_close_proof_overlay.name = "CloseProofOverlay"
	_close_proof_overlay.visible = false
	_close_proof_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_close_proof_overlay.position = Vector2.ZERO
	_close_proof_overlay.size = Vector2(1280.0, 720.0)
	_close_proof_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	_close_proof_layer.add_child(_close_proof_overlay)

	var overlay_card := ColorRect.new()
	overlay_card.name = "CloseProofCard"
	overlay_card.color = Color(0.95, 0.62, 0.14, 0.92)
	overlay_card.position = Vector2(44.0, 44.0)
	overlay_card.size = Vector2(420.0, 168.0)
	_close_proof_overlay.add_child(overlay_card)

	var overlay_accent := ColorRect.new()
	overlay_accent.name = "CloseProofAccent"
	overlay_accent.color = Color(0.16, 0.55, 0.95, 1.0)
	overlay_accent.position = Vector2(64.0, 68.0)
	overlay_accent.size = Vector2(88.0, 88.0)
	_close_proof_overlay.add_child(overlay_accent)

	var overlay_label := Label.new()
	overlay_label.name = "CloseProofLabel"
	overlay_label.text = "CLOSE PROOF"
	overlay_label.position = Vector2(176.0, 70.0)
	overlay_label.add_theme_color_override("font_color", Color(0.06, 0.08, 0.10, 1.0))
	overlay_label.add_theme_font_size_override("font_size", 28)
	_close_proof_overlay.add_child(overlay_label)

	var overlay_subtitle := Label.new()
	overlay_subtitle.name = "CloseProofSubtitle"
	overlay_subtitle.text = "proxy / cesium"
	overlay_subtitle.position = Vector2(176.0, 112.0)
	overlay_subtitle.add_theme_color_override("font_color", Color(0.10, 0.12, 0.16, 1.0))
	overlay_subtitle.add_theme_font_size_override("font_size", 18)
	_close_proof_overlay.add_child(overlay_subtitle)


func _build_proxy_scene() -> void:
	var earth_proxy := MeshInstance3D.new()
	var earth_mesh := SphereMesh.new()
	# Keep the control globe at the same physical scale as Cesium's WGS84 mesh.
	earth_mesh.radius = 2200.0
	earth_mesh.height = 4400.0
	earth_mesh.radial_segments = 48
	earth_mesh.rings = 24
	earth_proxy.mesh = earth_mesh
	var earth_material := StandardMaterial3D.new()
	earth_material.albedo_color = Color(0.18, 0.40, 0.78, 1.0)
	earth_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	earth_material.cull_mode = BaseMaterial3D.CULL_DISABLED
	earth_material.roughness = 1.0
	earth_proxy.material_override = earth_material
	_variant_root.add_child(earth_proxy)

	_add_debug_box(Vector3(700.0, 300.0, 300.0), DEBUG_BOX_POSITION, _variant_root)


func _build_cesium_plugin_scene() -> bool:
	if not await _wait_for_cesium_class("CesiumGeoreference", 6):
		_log("Cesium addon classes were not available")
		return false

	var cesium_globe = ClassDB.instantiate("CesiumGeoreference")
	if cesium_globe == null:
		_log("CesiumGeoreference could not be instantiated")
		return false

	cesium_globe.name = "CesiumGeoreference"
	cesium_globe.position = Vector3.ZERO
	var proof_origin := _cesium_engine_origin()
	if cesium_globe.has_method("set_ecef_x"):
		cesium_globe.set_ecef_x(proof_origin.x)
		cesium_globe.set_ecef_y(proof_origin.y)
		cesium_globe.set_ecef_z(proof_origin.z)
		_log("Cesium georeference origin ecef=%s" % str(proof_origin))
	_variant_root.add_child(cesium_globe)

	if not await _wait_for_cesium_class("Cesium3DTileset", 6):
		_log("Cesium3DTileset class was not available")
		return false
	var tileset = ClassDB.instantiate("Cesium3DTileset")
	if tileset == null:
		_log("Cesium3DTileset could not be instantiated")
		return false
	var token := _cesium_token()
	var url := OS.get_environment("CESIUM_3DTILES_URL").strip_edges()
	if token.is_empty() and url.is_empty():
		_cesium_failure = "CESIUM_ION_TOKEN or CESIUM_3DTILES_URL is required for Cesium-earth proof"
		_log(_cesium_failure)
		return false
	if not token.is_empty() and not _configure_cesium_token(token):
		return false
	tileset.name = "Cesium3DTileset"
	if not token.is_empty():
		if tileset.has_method("set_data_source"):
			# CesiumDataSource.FromCesiumIon is the native enum's zero value.
			tileset.set_data_source(0)
		if tileset.has_method("set_ion_asset_id"):
			tileset.set_ion_asset_id(1)

		if ClassDB.class_exists("CesiumIonRasterOverlay"):
			var imagery = ClassDB.instantiate("CesiumIonRasterOverlay")
			if imagery != null:
				imagery.name = "CesiumIonRasterOverlay"
				tileset.add_child(imagery)
				if imagery.has_method("set_asset_id"):
					imagery.set_asset_id(2)
		_cesium_source = "ion"
		_log("Cesium tileset scene built source=ion asset=1 imagery=2")
	elif not url.is_empty():
		if not tileset.has_method("set_data_source") or not tileset.has_method("set_url"):
			_cesium_failure = "Cesium3DTileset URL bindings are unavailable"
			_log(_cesium_failure)
			return false
		tileset.set_data_source(1)
		tileset.set_url(url)
		_cesium_configured = true
		_cesium_source = "url"
		_log("Cesium tileset scene built source=url url=%s" % url)
	_cesium_tileset = tileset
	_drive_cesium_initial_load = true
	# Configure the source and overlays before _ready() starts the native load.
	cesium_globe.add_child(tileset)

	_add_debug_box(Vector3(700.0, 300.0, 300.0), DEBUG_BOX_POSITION, _variant_root)
	# Keep an origin control in the Cesium lane so camera/visibility failures
	# cannot be confused with a missing remote tile request.
	_add_debug_box(Vector3(300.0, 180.0, 180.0), Vector3.ZERO, _variant_root)
	return true


func _cesium_token() -> String:
	var token := OS.get_environment("CESIUM_ION_ACCESS_TOKEN").strip_edges()
	if token.is_empty():
		token = OS.get_environment("CESIUM_ION_TOKEN").strip_edges()
	if token.is_empty():
		token = OS.get_environment("CESIUMION_TOKEN").strip_edges()
	return token


func _cesium_engine_origin() -> Vector3:
	var raw := OS.get_environment("CESIUM_PROOF_ENGINE_ORIGIN").strip_edges()
	if not raw.is_empty():
		var values := raw.split(",", false)
		if values.size() == 3:
			return Vector3(float(values[0]), float(values[1]), float(values[2]))
		_log("CESIUM_PROOF_ENGINE_ORIGIN must contain exactly three comma-separated numbers")
	return CESIUM_DEFAULT_ENGINE_ORIGIN


func _configure_cesium_token(token: String) -> bool:
	if not ClassDB.class_exists("CesiumGDConfig"):
		_log("CESIUM_TOKEN_CONFIG_CLASS_MISSING")
		return false
	var config = ClassDB.instantiate("CesiumGDConfig")
	if config == null or not config.has_method("set_access_token"):
		_log("CESIUM_TOKEN_CONFIG_UNAVAILABLE")
		return false
	_variant_root.add_child(config)
	config.set_access_token(token)
	_cesium_configured = true
	_log("CESIUM_TOKEN_CONFIGURED length=%d" % token.length())
	return true


func _wait_for_cesium_class(type_name: String, attempts: int) -> bool:
	for attempt in range(attempts):
		if ClassDB.class_exists(type_name):
			return true
		await get_tree().process_frame
		_log("waiting for %s to register (%d/%d)" % [type_name, attempt + 1, attempts])
	return ClassDB.class_exists(type_name)


func _capture_shot(name: String, camera_position: Vector3, look_at: Vector3, fov_degrees: float) -> bool:
	if not _proof_ready:
		_log("capture skipped before readiness: %s" % name)
		return false
	_close_proof_marker.visible = name.ends_with("_close")
	_close_proof_overlay.visible = name.ends_with("_close")
	var overlay_subtitle := _close_proof_overlay.get_node_or_null("CloseProofSubtitle")
	if overlay_subtitle != null:
		overlay_subtitle.text = name
	_log("capture setup %s marker_visible=%s camera=%s look_at=%s fov=%s" % [
		name,
		str(_close_proof_marker.visible),
		str(camera_position),
		str(look_at),
		str(fov_degrees),
	])
	_camera.global_position = camera_position
	_camera.fov = fov_degrees
	_camera.look_at(look_at, Vector3.UP)
	_camera.make_current()
	await get_tree().process_frame
	var active_camera := get_viewport().get_camera_3d()
	var origin_visible := not _camera.is_position_behind(Vector3.ZERO)
	var origin_screen := _camera.unproject_position(Vector3.ZERO)
	_log("CAMERA_STATE name=%s active=%s position=%s forward=%s origin_visible=%s origin_screen=%s viewport=%s" % [
		name,
		str(active_camera == _camera),
		str(_camera.global_position),
		str(-_camera.global_transform.basis.z),
		str(origin_visible),
		str(origin_screen),
		str(get_viewport().get_visible_rect().size),
	])
	if _close_proof_marker.visible:
		for frame in range(6):
			await RenderingServer.frame_post_draw
			_log("close settle frame %d/6 for %s" % [frame + 1, name])
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	var path := _capture_root.path_join("%s.png" % name)
	var saved := image.save_png(path)
	_log("captured %s -> %s (saved=%s)" % [name, path, saved])
	return saved == OK


func _capture_root_from_args() -> String:
	var args: Array[String] = []
	for arg in OS.get_cmdline_user_args():
		args.append(str(arg))
	for arg in OS.get_cmdline_args():
		var text := str(arg)
		if not args.has(text):
			args.append(text)
	for index in range(args.size()):
		var arg := args[index]
		if arg.begins_with("--capture-root="):
			return arg.split("=", false, 1)[1]
		if arg.begins_with("capture-root="):
			return arg.split("=", false, 1)[1]
		if arg == "--capture-root" and index + 1 < args.size():
			return str(args[index + 1])
		if arg == "capture-root" and index + 1 < args.size():
			return str(args[index + 1])
	return ""


func _proof_variants_from_args() -> Array[String]:
	var args: Array[String] = []
	for arg in OS.get_cmdline_user_args():
		args.append(str(arg))
	for arg in OS.get_cmdline_args():
		var text := str(arg)
		if not args.has(text):
			args.append(text)
	var variants: Array[String] = []
	for index in range(args.size()):
		var arg := args[index]
		if arg.begins_with("--proof-variants="):
			return _split_variants(arg.split("=", false, 1)[1])
		if arg.begins_with("proof-variants="):
			return _split_variants(arg.split("=", false, 1)[1])
		if arg == "--proof-variants" and index + 1 < args.size():
			return _split_variants(str(args[index + 1]))
		if arg == "proof-variants" and index + 1 < args.size():
			return _split_variants(str(args[index + 1]))
	return variants


func _split_variants(raw_variants: String) -> Array[String]:
	var variants: Array[String] = []
	for item in raw_variants.split(",", false):
		var variant := item.strip_edges()
		if not variant.is_empty():
			variants.append(variant)
	return variants


func _write_manifest() -> void:
	var manifest_path := _capture_root.path_join("visual_proof_manifest.json")
	var capture_paths: Array[String] = []
	for variant in PROOF_VARIANTS:
		for shot in SHOTS:
			capture_paths.append(_capture_root.path_join("%s_%s.png" % [str(variant["name"]), str(shot["name"])]))
	var lines: Array[String] = []
	lines.append("{")
	lines.append("  \"schema\": \"cesium.visual_proof_manifest.v1\",")
	lines.append("  \"generated_at\": \"%s\"," % Time.get_datetime_string_from_system(true, true))
	lines.append("  \"engine\": \"godot\",")
	lines.append("  \"host\": \"windows\",")
	lines.append("  \"native_target\": \"windows\",")
	lines.append("  \"architecture\": \"x86_64\",")
	lines.append("  \"capture_variants\": [\"proxy\", \"cesium\"],")
	lines.append("  \"cesium_configured\": %s," % str(_cesium_configured).to_lower())
	lines.append("  \"cesium_source\": \"%s\"," % _cesium_source)
	lines.append("  \"cesium_ready\": %s," % str(_cesium_ready).to_lower())
	lines.append("  \"cesium_renderer_count\": %d," % _cesium_renderer_count)
	lines.append("  \"cesium_tile_child_count\": %d," % _cesium_tile_child_count)
	lines.append("  \"shot_names\": [\"overview\", \"oblique\", \"close\"],")
	lines.append("  \"camera_shots\": [")
	for index in range(SHOTS.size()):
		var shot: Dictionary = SHOTS[index]
		var shot_suffix := "," if index + 1 < SHOTS.size() else ""
		lines.append("    {")
		lines.append("      \"name\": \"%s\"," % str(shot["name"]))
		var camera_position: Vector3 = shot["camera_position"]
		var look_at: Vector3 = shot["look_at"]
		lines.append("      \"camera_position\": [%s, %s, %s]," % [camera_position.x, camera_position.y, camera_position.z])
		lines.append("      \"look_at\": [%s, %s, %s]," % [look_at.x, look_at.y, look_at.z])
		lines.append("      \"fov_degrees\": %s" % str(shot["fov_degrees"]))
		lines.append("    }%s" % shot_suffix)
	lines.append("  ],")
	lines.append("  \"capture_paths\": [")
	for index in range(capture_paths.size()):
		var suffix := "," if index + 1 < capture_paths.size() else ""
		lines.append("    \"%s\"%s" % [capture_paths[index], suffix])
	lines.append("  ]")
	lines.append("}")
	var file := FileAccess.open(manifest_path, FileAccess.WRITE)
	if file != null:
		file.store_string("\n".join(lines))
		file.close()
		_log("Wrote visual proof manifest to %s" % manifest_path)


func _log(message: String) -> void:
	print(message)
	if _proof_log.is_empty():
		return
	var mode := FileAccess.READ_WRITE if FileAccess.file_exists(_proof_log) else FileAccess.WRITE
	var file := FileAccess.open(_proof_log, mode)
	if file == null:
		return
	if mode == FileAccess.READ_WRITE:
		file.seek_end()
	file.store_line(message)


func _add_debug_box(size: Vector3, origin: Vector3, parent: Node3D) -> void:
	var half := size * 0.5
	var faces := [
		{
			"name": "+X",
			"color": Color(0.95, 0.24, 0.24, 1.0),
			"size": Vector2(size.z, size.y),
			"position": origin + Vector3(half.x, 0.0, 0.0),
			"rotation_degrees": Vector3(0.0, 90.0, 0.0),
		},
		{
			"name": "-X",
			"color": Color(0.24, 0.93, 0.35, 1.0),
			"size": Vector2(size.z, size.y),
			"position": origin + Vector3(-half.x, 0.0, 0.0),
			"rotation_degrees": Vector3(0.0, -90.0, 0.0),
		},
		{
			"name": "+Y",
			"color": Color(0.25, 0.45, 0.97, 1.0),
			"size": Vector2(size.x, size.z),
			"position": origin + Vector3(0.0, half.y, 0.0),
			"rotation_degrees": Vector3(-90.0, 0.0, 0.0),
		},
		{
			"name": "-Y",
			"color": Color(0.95, 0.85, 0.25, 1.0),
			"size": Vector2(size.x, size.z),
			"position": origin + Vector3(0.0, -half.y, 0.0),
			"rotation_degrees": Vector3(90.0, 0.0, 0.0),
		},
		{
			"name": "+Z",
			"color": Color(0.90, 0.34, 0.90, 1.0),
			"size": Vector2(size.x, size.y),
			"position": origin + Vector3(0.0, 0.0, half.z),
			"rotation_degrees": Vector3(0.0, 0.0, 0.0),
		},
		{
			"name": "-Z",
			"color": Color(0.22, 0.86, 0.88, 1.0),
			"size": Vector2(size.x, size.y),
			"position": origin + Vector3(0.0, 0.0, -half.z),
			"rotation_degrees": Vector3(0.0, 180.0, 0.0),
		},
	]

	for face in faces:
		var face_mesh := MeshInstance3D.new()
		face_mesh.name = "DebugFace_%s" % face["name"]
		var quad := QuadMesh.new()
		quad.size = face["size"]
		face_mesh.mesh = quad
		face_mesh.position = face["position"]
		face_mesh.rotation_degrees = face["rotation_degrees"]
		var material := StandardMaterial3D.new()
		material.albedo_color = face["color"]
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.roughness = 0.35
		material.cull_mode = BaseMaterial3D.CULL_DISABLED
		face_mesh.material_override = material
		parent.add_child(face_mesh)
