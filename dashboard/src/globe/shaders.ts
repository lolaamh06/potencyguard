// GLSL for the globe. Colours arrive as uniforms taken from the design tokens.

/** Land dots: round soft points that fade out on the far side of the sphere. */
export const DOT_VERTEX = /* glsl */ `
  uniform float uSize;
  uniform float uPixelRatio;
  varying float vFacing;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vec3 n = normalize(normalMatrix * position);
    vFacing = dot(n, normalize(-mv.xyz));
    gl_PointSize = uSize * uPixelRatio / max(-mv.z, 0.2);
    gl_Position = projectionMatrix * mv;
  }
`;

export const DOT_FRAGMENT = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  varying float vFacing;
  void main() {
    vec2 c = gl_PointCoord - 0.5;
    float d = length(c);
    float disc = 1.0 - smoothstep(0.28, 0.5, d);
    float facing = smoothstep(0.02, 0.4, vFacing);
    float a = disc * facing * uOpacity;
    if (a < 0.01) discard;
    gl_FragColor = vec4(uColor * (0.7 + 0.5 * facing), a);
  }
`;

/** The dark ball under the dots: hides the far side and the back of the route, with a faint rim. */
export const BODY_VERTEX = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vViewDir;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vViewDir = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`;

export const BODY_FRAGMENT = /* glsl */ `
  uniform vec3 uBase;
  uniform vec3 uRim;
  varying vec3 vNormal;
  varying vec3 vViewDir;
  void main() {
    float f = pow(1.0 - abs(dot(normalize(vNormal), normalize(vViewDir))), 2.5);
    gl_FragColor = vec4(mix(uBase, uRim, f * 0.35), 1.0);
  }
`;

/** Atmosphere: a soft fresnel rim on a slightly larger back-facing shell. */
export const ATMOSPHERE_FRAGMENT = /* glsl */ `
  uniform vec3 uColor;
  uniform float uStrength;
  varying vec3 vNormal;
  varying vec3 vViewDir;
  void main() {
    float f = pow(1.0 - abs(dot(normalize(vNormal), normalize(vViewDir))), 4.0);
    gl_FragColor = vec4(uColor, f * uStrength);
  }
`;

/** Route: a tube coloured by state, with a moving pulse, dashing for the alternative, and the
 *  part beyond the shipment's progress dimmed. vT runs 0 to 1 along the route. */
export const ROUTE_VERTEX = /* glsl */ `
  varying float vT;
  void main() {
    vT = uv.x;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

export const ROUTE_FRAGMENT = /* glsl */ `
  uniform vec3 uColor;
  uniform float uTime;
  uniform float uDashed;
  uniform float uProgress;
  varying float vT;
  void main() {
    if (uDashed > 0.5 && fract(vT * 70.0) > 0.5) discard;
    float d = fract(vT - uTime * 0.12);
    float pulse = smoothstep(0.0, 0.015, d) * (1.0 - smoothstep(0.015, 0.1, d));
    float done = 1.0 - smoothstep(uProgress, uProgress + 0.004, vT);
    float base = mix(0.32, 0.95, done);
    gl_FragColor = vec4(uColor * (1.0 + pulse * 1.1), clamp(base + pulse * 0.5, 0.0, 1.0));
  }
`;
