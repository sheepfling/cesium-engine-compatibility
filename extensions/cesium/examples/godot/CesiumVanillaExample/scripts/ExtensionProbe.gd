extends SceneTree


func _init() -> void:
	for name in ["CesiumGeoreference", "Cesium3DTileset", "CesiumIonRasterOverlay"]:
		print("%s registered: %s" % [name, ClassDB.class_exists(name)])
	quit()
