shader_type spatial;

render_mode cull_disabled, diffuse_burley, specular_disabled;

uniform sampler2D albedo_texture : source_color;
uniform vec2 uv_offset = vec2(0.0);
uniform vec2 uv_scale = vec2(1.0);
uniform float uv_rotation = 0.0;

void vertex() {
	vec2 uv = UV * uv_scale + uv_offset;
	vec2 pivoted = uv - vec2(0.5);
	float sine = sin(uv_rotation);
	float cosine = cos(uv_rotation);
	UV = vec2(
		pivoted.x * cosine - pivoted.y * sine,
		pivoted.x * sine + pivoted.y * cosine
	) + vec2(0.5);
}

void fragment() {
	ALBEDO = texture(albedo_texture, UV).rgb;
	ALPHA = texture(albedo_texture, UV).a;
}
