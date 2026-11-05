#version 440
// Siri-style glow hugging the screen edges, flowing around the perimeter.
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;
    float level;
    float aspect;   // width / height
};

vec3 palette(float t) {
    vec3 a = vec3(0.55, 0.5, 0.75), b = vec3(0.45, 0.4, 0.3);
    vec3 c = vec3(1.0, 1.0, 1.0), d = vec3(0.55, 0.33, 0.0);
    return a + b * cos(6.28318 * (c * t + d));
}

void main() {
    vec2 uv = qt_TexCoord0;
    vec2 px = vec2(uv.x * aspect, uv.y);
    float dx = min(px.x, aspect - px.x);
    float dy = min(px.y, 1.0 - px.y);
    float d = min(dx, dy);

    // position along the perimeter, 0..1
    float per;
    if (d == dy && uv.y < 0.5) per = px.x;
    else if (d == dx && uv.x > 0.5) per = aspect + px.y;
    else if (d == dy) per = aspect + 1.0 + (aspect - px.x);
    else per = 2.0 * aspect + 1.0 + (1.0 - px.y);
    per /= 2.0 * (aspect + 1.0);

    float wave = 0.5 + 0.5 * sin(per * 6.28318 * 3.0 - time * 2.0);
    float width = 0.010 + 0.022 * level + 0.008 * wave;
    float g = exp(-d / width);
    float line = exp(-d / 0.0025);
    vec3 col = palette(per * 2.0 - time * 0.18);
    float a = clamp(g * (0.55 + level * 0.6) + line * 0.6, 0.0, 1.0);
    fragColor = vec4(col * a, a) * qt_Opacity;
}
