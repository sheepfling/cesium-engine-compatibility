extends Node

func _ready() -> void:
	print("PRINT_ARGS_OK")
	for arg in OS.get_cmdline_user_args():
		print(arg)
	get_tree().quit()
