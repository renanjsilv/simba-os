#version 440
// Minimal voice line: a few glowing sine strands that swell with the voice.
// spread = 0..1, how far the line has grown out from the center.
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;
    float level;
    float spread;
};

const float PI = 3.14159265;

vec3 strand(vec2 uv, float env, float amp, float freq, float speed, float phase, vec3 col) {
    float y = 0.5 + amp * env * sin(uv.x * freq + time * speed + phase);
    float d = abs(uv.y - y);
    float core = exp(-d * d / 0.00045);
    float glow = exp(-d * 9.0) * 0.35;
    return col * (core + glow);
}

void main() {
    vec2 uv = qt_TexCoord0;
    float x = uv.x - 0.5;
    float reach = max(spread, 0.001) * 0.5;
    float env = pow(max(cos(clamp(x / reach, -1.0, 1.0) * PI * 0.5), 0.0), 1.6);
    if (abs(x) > reach) env = 0.0;

    float amp = 0.05 + level * 0.36;
    vec3 c = vec3(0.0);
    c += strand(uv, env, amp,        14.0,  3.1, 0.0, vec3(0.20, 0.80, 1.00));
    c += strand(uv, env, amp * 0.8,  19.0, -2.4, 1.7, vec3(0.65, 0.35, 1.00));
    c += strand(uv, env, amp * 0.6,  11.0,  4.2, 3.9, vec3(1.00, 0.35, 0.65));
    c *= env;

    float a = clamp(max(max(c.r, c.g), c.b), 0.0, 1.0);
    fragColor = vec4(min(c, vec3(1.0)), a) * qt_Opacity;
}
