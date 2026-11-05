#version 440
// Draco orb: a glass sphere with soft colored lights drifting inside it.
// level = smoothed voice amplitude (0..1)
// think = 0..1 blend into the "processing" swirl
// speak = 0..1 blend into the "answering" pulse
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;
    float level;
    float think;
    float speak;
    float spin;   // phase of the interior lights, integrated in QML (speed changes stay smooth)
};

const float TAU = 6.2831853;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x),
               mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
// Seamless noise around the circle: sample along a ring in noise space.
float ringNoise(float ang, float radius, float t) {
    vec2 c = vec2(cos(ang), sin(ang)) * radius;
    return noise(c + vec2(t, -t * 0.7)) * 0.65 + noise(c * 2.1 - vec2(t * 1.3, t)) * 0.35;
}

// A soft light blob orbiting inside the sphere.
vec3 light(vec2 q, vec3 col, float speed, float phase, float orbit, float size, float t) {
    float a = t * speed + phase;
    vec2 c = vec2(cos(a), sin(a * 1.31 + phase)) * orbit;
    float d = length(q - c);
    return col * exp(-d * d / (size * size));
}

void main() {
    vec2 p = qt_TexCoord0 * 2.0 - 1.0;
    float t = time;
    float ang = atan(p.y, p.x);
    float d = length(p);
    float lv = level;

    // Living silhouette: the edge breathes and ripples with the voice.
    float wob = ringNoise(ang, 1.3, t * 0.3) - 0.5;
    float ripple = sin(ang * 3.0 + t * 1.4) * 0.5 + sin(ang * 5.0 - t * 1.9) * 0.5;
    float r = 0.50
            + 0.025 * sin(t * 1.3)
            + lv * 0.12
            + wob * (0.035 + lv * 0.14)
            + ripple * lv * 0.03 * (1.0 - think);
    r *= mix(1.0, 0.86 + 0.035 * sin(t * 2.0), think);

    vec2 q = p / max(r, 0.001);
    float qd = length(q);

    // Interior lights; they speed up while thinking and flare with the voice.
    float tt = spin;
    float grow = 1.0 + lv * 0.35;
    vec3 inner = vec3(0.03, 0.03, 0.10);
    inner += light(q, vec3(0.15, 0.80, 1.00), 0.53, 0.0, 0.48, 0.62 * grow, tt);
    inner += light(q, vec3(0.30, 0.38, 1.00), 0.41, 2.1, 0.55, 0.70 * grow, tt);
    inner += light(q, vec3(0.70, 0.30, 1.00), 0.37, 4.2, 0.50, 0.60 * grow, tt);
    inner += light(q, vec3(1.00, 0.30, 0.62), 0.61, 1.0, 0.58, 0.52 * grow, tt);
    inner += light(q, vec3(1.00, 0.60, 0.25), 0.47, 3.3, 0.62, 0.40 * grow, tt) * (0.6 + lv);

    // Gauzy turbulence so the lights look like they're inside fluid.
    float n = noise(q * 2.2 + vec2(t * 0.35, -t * 0.28));
    inner *= 0.80 + 0.40 * n;

    // Processing: a bright comet arc sweeping around the rim.
    float sweep = fract(ang / TAU - t * 0.3);  // ~1 turn every 3 s
    float arc = pow(sweep, 6.0) * smoothstep(1.0, 0.93, sweep) * think;

    // Glass: fresnel rim, soft core shading, a specular highlight.
    float z = sqrt(max(1.0 - qd * qd, 0.0));
    float fres = pow(1.0 - z, 2.5);
    vec3 rimCol = mix(vec3(0.75, 0.88, 1.0), inner * 1.6, 0.55);
    inner *= 0.65 + 0.35 * z;
    inner *= 1.0 + lv * 0.6 + speak * 0.15;
    inner += rimCol * fres * (0.8 + lv * 0.8);
    inner += vec3(1.0, 0.95, 1.0) * arc * fres * 1.8;
    // filmic-ish roll-off so overlapping lights never clip to flat white
    inner = 1.0 - exp(-inner * 1.25);
    vec2 hl = q - vec2(-0.32, -0.40);
    inner += vec3(1.0) * exp(-dot(hl, hl) * 14.0) * 0.28;

    float aa = 2.0 / 200.0;
    float body = 1.0 - smoothstep(r - aa, r + aa, d);

    // Halo outside the sphere, tinted by the direction (seamless).
    float outside = max(d - r, 0.0);
    float glowAmt = (0.45 + lv * 1.3 + think * 0.35) * exp(-outside * (10.0 - lv * 4.5));
    vec3 glowCol = vec3(0.35, 0.55, 1.0)
                 + 0.35 * vec3(cos(ang + t * 0.6), cos(ang + t * 0.6 + 2.1), cos(ang + t * 0.6 + 4.2));
    glowCol = max(glowCol, 0.0) * glowAmt;
    glowCol += vec3(0.9, 0.8, 1.0) * arc * exp(-outside * 22.0);

    vec3 rgb = inner * body + glowCol * (1.0 - body);
    float a = max(body, clamp(glowAmt * 0.8, 0.0, 1.0));
    float edge = 1.0 - smoothstep(0.88, 1.0, d);
    fragColor = vec4(rgb * edge, a * edge) * qt_Opacity;   // premultiplied
}
