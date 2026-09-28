class_name Player
extends CharacterBody2D
## The player character: runs left/right and jumps.

signal died(cause: String)

const JUMP_VELOCITY := -400.0

@export var speed := 200.0
var lives := 3


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity += get_gravity() * delta
	var direction := Input.get_axis("ui_left", "ui_right")
	velocity.x = direction * speed
	move_and_slide()


func hurt() -> void:
	lives -= 1
	if lives <= 0:
		died.emit("out of lives")
